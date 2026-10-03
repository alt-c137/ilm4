"""Голосовые комнаты сообществ: кто сейчас в комнате и обмен сигналами WebRTC.

Звук идёт напрямую между участниками (каждый с каждым) — сервер только знакомит их и следит за правами.
Этого хватает на небольшую комнату (до MAX_PEERS человек). Для больших комнат, демонстрации экрана и записи нужен
медиасервер (SFU, например LiveKit): тогда меняются только клиент и выдача токена — комнаты, права и список
присутствующих остаются как есть.

Кто в комнате — в кеше (общем для всех процессов сайта): {peer: {id, name, avatar, muted, seen}}; запись живёт TTL секунд
и продлевается «пульсом» клиента, так что упавшая вкладка сама исчезает из списка.
"""
import secrets
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.core.cache import cache

MAX_PEERS = 8
TTL = 75


def _key(voice_id) -> str:
    return f'voice:{voice_id}'


def _load(voice_id) -> dict:
    now = time.time()
    data = cache.get(_key(voice_id)) or {}
    return {p: v for p, v in data.items() if now - v.get('seen', 0) < TTL}


def present(voice_id) -> list:
    """Кто сейчас в комнате: [{'peer','id','name','avatar','muted'}]."""
    return [{'peer': p, **{k: v[k] for k in ('id', 'name', 'avatar', 'muted')}} for p, v in _load(voice_id).items()]


def enter(voice_id, peer: str, info: dict) -> None:
    data = _load(voice_id)
    data[peer] = {**info, 'muted': False, 'seen': time.time()}
    cache.set(_key(voice_id), data, TTL * 4)


def touch(voice_id, peer: str, muted=None) -> None:
    data = _load(voice_id)
    if peer in data:
        data[peer]['seen'] = time.time()
        if muted is not None:
            data[peer]['muted'] = bool(muted)
        cache.set(_key(voice_id), data, TTL * 4)


def leave(voice_id, peer: str) -> None:
    data = _load(voice_id)
    if data.pop(peer, None) is not None:
        cache.set(_key(voice_id), data, TTL * 4)


def ice_servers() -> list:
    """Серверы для установления соединения: открытый STUN и свой TURN из настроек сайта (если задан)."""
    from apps.core.models import SiteSettings
    st = SiteSettings.get_solo()
    out = [{'urls': 'stun:stun.l.google.com:19302'}]
    if st.webrtc_turn_url:
        out.append({'urls': st.webrtc_turn_url, 'username': st.webrtc_turn_username, 'credential': st.webrtc_turn_credential})
    return out


class VoiceConsumer(AsyncJsonWebsocketConsumer):
    """ws/voice/<id>/ — вход в голосовую комнату: список присутствующих, сигналы WebRTC адресату, «микрофон выключен»."""

    async def connect(self):
        self.user = self.scope['user']
        self.voice_id = int(self.scope['url_route']['kwargs']['voice_id'])
        self.group, self.peer, self.inside = f'voice_{self.voice_id}', secrets.token_hex(6), False
        info = await self._allowed() if self.user.is_authenticated else None
        if info is None:
            await self.close()
            return
        await self.accept()
        peers = await database_sync_to_async(present)(self.voice_id)
        if len(peers) >= MAX_PEERS:
            await self.send_json({'type': 'full', 'max': MAX_PEERS})
            await self.close()
            return
        await database_sync_to_async(enter)(self.voice_id, self.peer, info)
        self.inside, self.info = True, info
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.send_json({'type': 'hello', 'me': self.peer, 'peers': peers, 'ice': await database_sync_to_async(ice_servers)()})
        await self.channel_layer.group_send(self.group, {'type': 'voice.joined', 'peer': self.peer, **info})

    @database_sync_to_async
    def _allowed(self):
        from . import spaces
        from .models import SpaceVoice
        room = SpaceVoice.objects.select_related('space').filter(pk=self.voice_id).first()
        if room is None or room.space.closed or not spaces.enabled():
            return None
        m = spaces.membership(room.space, self.user)
        if m is None:
            return None
        return {'id': self.user.pk, 'name': m.nick or self.user.get_display_name(), 'avatar': self.user.avatar.url if self.user.avatar else ''}

    async def disconnect(self, code):
        if getattr(self, 'inside', False):
            await database_sync_to_async(leave)(self.voice_id, self.peer)
            await self.channel_layer.group_discard(self.group, self.channel_name)
            await self.channel_layer.group_send(self.group, {'type': 'voice.left', 'peer': self.peer})

    async def receive_json(self, content):
        if not getattr(self, 'inside', False):
            return
        kind = content.get('type')
        if kind == 'signal' and isinstance(content.get('to'), str) and isinstance(content.get('data'), dict):
            data = {k: content['data'].get(k) for k in ('sdp', 'candidate') if k in content['data']}
            await self.channel_layer.group_send(self.group, {'type': 'voice.signal', 'to': content['to'], 'from': self.peer, 'data': data})
        elif kind == 'state':
            muted = bool(content.get('muted'))
            await database_sync_to_async(touch)(self.voice_id, self.peer, muted)
            await self.channel_layer.group_send(self.group, {'type': 'voice.state', 'peer': self.peer, 'muted': muted})
        elif kind == 'ping':
            await database_sync_to_async(touch)(self.voice_id, self.peer)

    async def voice_joined(self, event):
        if event['peer'] != self.peer:
            await self.send_json({'type': 'joined', **{k: event[k] for k in ('peer', 'id', 'name', 'avatar')}})

    async def voice_left(self, event):
        await self.send_json({'type': 'left', 'peer': event['peer']})

    async def voice_state(self, event):
        await self.send_json({'type': 'state', 'peer': event['peer'], 'muted': event['muted']})

    async def voice_signal(self, event):
        if event['to'] == self.peer:
            await self.send_json({'type': 'signal', 'from': event['from'], 'data': event['data']})
