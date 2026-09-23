"""Перенос раздела «Никях» в отдельную установку (и обратно).

    python manage.py nikah_export nikah.zip     # на старом сервере
    python manage.py nikah_import nikah.zip     # на новом (SITE_MODE=nikah)

В архиве: data.enc — анкеты, интересы, пропуски, закладки, пары и их переписка,
аккаунты владельцев (email, хеш пароля, Telegram), всё зашифровано ключом
CHAT_ENCRYPTION_KEY; files/ — фото анкет (они и так хранятся зашифрованными).
Поэтому на новом сервере должен стоять ТОТ ЖЕ CHAT_ENCRYPTION_KEY.
Баланс кошелька и платежи не переносятся — их сверяют вручную.
"""
import json
import zipfile

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils.dateparse import parse_datetime

from apps.chat.crypto import decrypt_bytes, encrypt_bytes
from apps.chat.models import Message, Thread

from .models import NikahInterest, NikahMatch, NikahProfile, NikahSaved, NikahSkip

VERSION = 1
USER_FIELDS = ('email', 'username', 'first_name', 'last_name', 'nickname', 'city', 'password', 'is_active',
               'telegram_id', 'telegram_username', 'date_joined')
SKIP_PROFILE = {'id', 'user', 'photo', 'photo_private'}
SKIP_MATCH = {'id', 'sister', 'brother', 'thread', 'sister_tg_msg', 'brother_tg_msg'}


def _plain(obj, skip):
    out = {}
    for f in obj._meta.concrete_fields:
        if f.name in skip:
            continue
        value = getattr(obj, f.attname)
        out[f.attname] = value.isoformat() if hasattr(value, 'isoformat') else value
    return out


def export_zip(path) -> dict:
    profiles = list(NikahProfile.objects.select_related('user'))
    users = {p.user_id: p.user for p in profiles}
    data = {'version': VERSION, 'users': [], 'profiles': [], 'interests': [], 'skips': [], 'saved': [],
            'matches': []}
    for u in users.values():
        row = {f: getattr(u, f) for f in USER_FIELDS}
        row['date_joined'] = u.date_joined.isoformat()
        row['id'] = u.pk
        data['users'].append(row)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in profiles:
            row = _plain(p, SKIP_PROFILE)
            row.update(id=p.pk, user=p.user_id, photo_file='')
            if p.photo_private:
                name = f'files/{p.pk}.bin'
                with p.photo_private.open('rb') as f:
                    z.writestr(name, f.read())
                row['photo_file'] = name
            data['profiles'].append(row)
        data['interests'] = list(NikahInterest.objects.values('from_profile_id', 'to_profile_id'))
        data['skips'] = list(NikahSkip.objects.values('from_profile_id', 'to_profile_id'))
        data['saved'] = [{'user': s.user_id, 'profile': s.profile_id}
                         for s in NikahSaved.objects.filter(user_id__in=users)]
        for m in NikahMatch.objects.all():
            row = _plain(m, SKIP_MATCH)
            row.update(sister=m.sister_id, brother=m.brother_id, messages=[])
            if m.thread_id:
                row['messages'] = [
                    {'sender': msg.sender_id, 'kind': msg.kind, 'body': msg.body,
                     'created_at': msg.created_at.isoformat(), 'read': bool(msg.read_at)}
                    for msg in m.thread.messages.filter(kind__in=[Message.TEXT, Message.SYSTEM])]
            data['matches'].append(row)
        z.writestr('data.enc', encrypt_bytes(json.dumps(data, ensure_ascii=False, default=str).encode()))
    return {k: len(v) for k, v in data.items() if isinstance(v, list)}


@transaction.atomic
def import_zip(path) -> dict:
    User = get_user_model()
    report = {'users_new': 0, 'users_linked': 0, 'profiles': 0, 'profiles_skipped': 0, 'matches': 0}
    with zipfile.ZipFile(path) as z:
        data = json.loads(decrypt_bytes(z.read('data.enc')))
        uid, pid = {}, {}
        for row in data['users']:
            user = User.objects.filter(email__iexact=row['email']).first()
            if user:
                report['users_linked'] += 1
            else:
                username = row['username']
                while User.objects.filter(username=username).exists():
                    username += '_n'
                tg = row['telegram_id'] if row['telegram_id'] and not User.objects.filter(
                    telegram_id=row['telegram_id']).exists() else None
                user = User(**{f: row[f] for f in USER_FIELDS if f not in ('date_joined', 'username', 'telegram_id')},
                            username=username, telegram_id=tg, date_joined=parse_datetime(row['date_joined']))
                user.save()
                report['users_new'] += 1
            uid[row['id']] = user
        for row in data['profiles']:
            user = uid[row.pop('user')]
            old_id, photo = row.pop('id'), row.pop('photo_file')
            if hasattr(user, 'nikah_profile'):
                pid[old_id] = user.nikah_profile
                report['profiles_skipped'] += 1
                continue
            for key in ('boosted_until', 'premium_until', 'last_seen', 'agreed_at', 'created_at', 'updated_at'):
                row[key] = parse_datetime(row[key]) if row.get(key) else None
            p = NikahProfile(user=user, **{k: v for k, v in row.items() if k not in ('created_at', 'updated_at')})
            if photo:
                p.photo_private.save(f'{old_id}.bin', ContentFile(z.read(photo)), save=False)
            p.save()
            if row.get('created_at'):
                NikahProfile.objects.filter(pk=p.pk).update(created_at=row['created_at'])
            pid[old_id] = p
            report['profiles'] += 1
        for model, key in ((NikahInterest, 'interests'), (NikahSkip, 'skips')):
            for row in data[key]:
                a, b = pid.get(row['from_profile_id']), pid.get(row['to_profile_id'])
                if a and b:
                    model.objects.get_or_create(from_profile=a, to_profile=b)
        for row in data['saved']:
            if row['user'] in uid and row['profile'] in pid:
                NikahSaved.objects.get_or_create(user=uid[row['user']], profile=pid[row['profile']])
        for row in data['matches']:
            sister, brother = pid.get(row.pop('sister')), pid.get(row.pop('brother'))
            msgs = row.pop('messages')
            if not (sister and brother):
                continue
            for key in ('sister_viewed_at', 'brother_viewed_at', 'created_at', 'closed_at'):
                row[key] = parse_datetime(row[key]) if row.get(key) else None
            created = row.pop('created_at')
            m, made = NikahMatch.objects.get_or_create(sister=sister, brother=brother, defaults=row)
            if made and msgs:
                t = Thread.objects.create(subject='Никях · знакомство')
                t.participants.add(sister.user, brother.user)
                for msg in msgs:
                    sender = uid.get(msg['sender'])
                    if sender:
                        new = Message.objects.create(thread=t, sender=sender, kind=msg['kind'], body=msg['body'])
                        Message.objects.filter(pk=new.pk).update(
                            created_at=parse_datetime(msg['created_at']),
                            read_at=parse_datetime(msg['created_at']) if msg['read'] else None)
                m.thread = t
                m.save(update_fields=['thread'])
            if made and created:
                NikahMatch.objects.filter(pk=m.pk).update(created_at=created)
            report['matches'] += made
    return report
