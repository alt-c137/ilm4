"""Маршруты WebSocket (подключаются в config/asgi.py)."""
from django.urls import re_path

from . import consumers, voice

websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<thread_id>\d+)/$', consumers.ChatConsumer.as_asgi()),
    re_path(r'ws/me/$', consumers.UserConsumer.as_asgi()),
    re_path(r'ws/voice/(?P<voice_id>\d+)/$', voice.VoiceConsumer.as_asgi()),
]
