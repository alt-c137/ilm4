"""Мессенджер v2: ключ на каждый чат, файлы, смена ключа, части ключа, отложенные и тихие
сообщения, переписка по жалобе, эмодзи звонка (docs/MESSENGER.md)."""
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import timedelta
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.utils import timezone

from apps.chat import keyring, services
from apps.chat.models import Message, Thread, ThreadKey

User = get_user_model()
pytestmark = pytest.mark.django_db
ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def pair(db):
    from apps.core.models import ModuleConfig
    ModuleConfig.objects.update_or_create(key='chat', defaults={'name': 'Чат', 'status': 'on'})
    a = User.objects.create_user('a', 'a@x.com', 'x')
    b = User.objects.create_user('b', 'b@x.com', 'x')
    return a, b, services.open_direct(a, b)


def _raw_body(pk):
    with connection.cursor() as c:
        c.execute('select body from chat_message where id = %s', [pk])
        return c.fetchone()[0]


# ---------- ключи ----------

def test_each_chat_has_own_key_and_ciphertext_is_bound_to_chat(pair):
    a, _b, t1 = pair
    c = User.objects.create_user('c', 'c@x.com', 'x')
    t2 = services.open_direct(a, c)
    m1 = Message.objects.create(thread=t1, sender=a, body='Ассаляму алейкум')
    Message.objects.create(thread=t2, sender=a, body='другой чат')
    k1, k2 = ThreadKey.objects.get(thread=t1), ThreadKey.objects.get(thread=t2)
    assert k1.wrapped != k2.wrapped and keyring.dek_for(t1.pk) != keyring.dek_for(t2.pk)
    assert 'Ассаляму' not in _raw_body(m1.pk)
    # шифротекст из одного чата, подложенный в другой, не расшифруется (AAD)
    assert keyring.decrypt_text(t2.pk, _raw_body(m1.pk)) == '[сообщение не удалось расшифровать]'
    assert Message.objects.get(pk=m1.pk).body == 'Ассаляму алейкум'


def test_master_key_rotation(pair, settings):
    a, _b, t = pair
    old, new = keyring.generate_master_key(), keyring.generate_master_key()
    settings.CHAT_MASTER_KEYS = f'k1:{old}'
    keyring.forget_cache()
    m = Message.objects.create(thread=t, sender=a, body='до смены ключа')
    settings.CHAT_MASTER_KEYS = f'k2:{new},k1:{old}'
    keyring.forget_cache()
    call_command('chat_keys', 'rotate')
    assert ThreadKey.objects.get(thread=t).kid == 'k2'
    settings.CHAT_MASTER_KEYS = f'k2:{new}'           # старый ключ убрали — всё читается
    keyring.forget_cache()
    assert Message.objects.get(pk=m.pk).body == 'до смены ключа'


def test_wrong_master_key_reads_nothing(pair, settings):
    a, _b, t = pair
    settings.CHAT_MASTER_KEYS = f'k1:{keyring.generate_master_key()}'
    keyring.forget_cache()
    m = Message.objects.create(thread=t, sender=a, body='тайна')
    settings.CHAT_MASTER_KEYS = f'k1:{keyring.generate_master_key()}'     # «украли базу», ключ другой
    keyring.forget_cache()
    assert Message.objects.get(pk=m.pk).body == '[сообщение не удалось расшифровать]'


def test_split_and_join_master_key(settings, capsys):
    key = keyring.generate_master_key()
    settings.CHAT_MASTER_KEYS = f'k7:{key}'
    keyring.forget_cache()
    call_command('chat_keys', 'split')
    shares = re.findall(r'k7:ilm4-share-\S+', capsys.readouterr().out)
    assert len(shares) == 3
    call_command('chat_keys', 'join', shares[0], shares[2])
    assert capsys.readouterr().out.strip() == f'k7:{key}'


def test_migrate_old_messages_and_files(pair, settings, tmp_path):
    from apps.chat.crypto import encrypt as legacy_encrypt
    settings.MEDIA_ROOT = tmp_path
    a, _b, t = pair
    m = Message.objects.create(thread=t, sender=a, body='x')
    Message.objects.filter(pk=m.pk).update(body_enc=legacy_encrypt('старый формат'))
    f = Message.objects.create(thread=t, sender=a, kind='photo')
    f.attachment.save('old.jpg', SimpleUploadedFile('old.jpg', b'\xff\xd8 plain jpeg'), save=True)
    call_command('chat_keys', 'migrate')
    assert _raw_body(m.pk).startswith('enc2:')
    assert Message.objects.get(pk=m.pk).body == 'старый формат'
    f.refresh_from_db()
    assert f.attachment.name.endswith('.jpg.enc') and not os.path.exists(tmp_path / 'old.jpg')


def test_encrypted_file_range_requests(pair, settings, tmp_path, client):
    from django.core.files.base import ContentFile

    from apps.chat.filecrypt import seal
    settings.MEDIA_ROOT = tmp_path
    a, _b, t = pair
    data = os.urandom(200_000)                       # больше трёх кусков по 64 КБ
    m = Message(thread=t, sender=a, kind='voice', duration=3)
    m.attachment.save('v.ogg.enc', ContentFile(seal(t.pk, data)), save=False)
    m.save()
    client.force_login(a)
    full = client.get(f'/chat/file/{m.pk}/')
    assert b''.join(full.streaming_content) == data and full['Content-Type'] == 'audio/ogg'
    part = client.get(f'/chat/file/{m.pk}/', HTTP_RANGE='bytes=65000-140000')
    assert part.status_code == 206 and part['Content-Range'] == f'bytes 65000-140000/{len(data)}'
    assert b''.join(part.streaming_content) == data[65000:140001]


# ---------- отложенные и тихие ----------

def test_scheduled_message_hidden_until_due(pair, client):
    from apps.core.models import Notification
    a, b, t = pair
    when = timezone.now() + timedelta(hours=1)
    p = services.send_text(t, a, 'Напомню завтра', schedule=when.isoformat())
    assert p['scheduled'] is True
    assert not services.visible_messages(t, b).filter(pk=p['id']).exists()     # собеседник не видит
    assert services.visible_messages(t, a).filter(pk=p['id']).exists()         # автор видит
    assert not Notification.objects.filter(user=b).exists()
    assert services.deliver_due() == 0
    assert services.deliver_due(now=when + timedelta(seconds=1)) == 1
    m = Message.objects.get(pk=p['id'])
    assert m.scheduled_at is None and services.visible_messages(t, b).filter(pk=m.pk).exists()
    assert Notification.objects.filter(user=b).exists()


def test_scheduled_send_now_and_cancel_by_author_only(pair, client):
    a, b, t = pair
    p1 = services.send_text(t, a, 'один', schedule=(timezone.now() + timedelta(days=1)).isoformat())
    p2 = services.send_text(t, a, 'два', schedule=(timezone.now() + timedelta(days=1)).isoformat())
    client.force_login(b)
    assert client.post(f'/chat/msg/{p1["id"]}/send/').status_code == 404       # чужое — нельзя
    client.force_login(a)
    assert client.post(f'/chat/msg/{p1["id"]}/send/').json()['scheduled'] is False
    assert client.post(f'/chat/msg/{p2["id"]}/cancel/').json()['ok'] is True
    assert not Message.objects.filter(pk=p2['id']).exists()


def test_silent_message_makes_silent_push(pair, monkeypatch, django_capture_on_commit_callbacks):
    from apps.api import push
    sent = []
    monkeypatch.setattr(push, 'send_to_user', lambda uid, body, url='', title='ilm4', silent=False: sent.append(silent))
    a, _b, t = pair
    with django_capture_on_commit_callbacks(execute=True):
        services.send_text(t, a, 'тихо', silent=True)
        services.send_text(t, a, 'громко')
    assert sent == [True, False]


def test_schedule_validation(pair):
    a, _b, t = pair
    with pytest.raises(services.ChatError):
        services.send_text(t, a, 'x', schedule=(timezone.now() + timedelta(days=400)).isoformat())
    p = services.send_text(t, a, 'прошлое время — сразу', schedule=(timezone.now() - timedelta(hours=1)).isoformat())
    assert p['scheduled'] is False


# ---------- переписка по жалобе ----------

def test_moderator_reads_chat_only_by_report_and_it_is_logged(pair, client):
    from django.contrib.contenttypes.models import ContentType
    from django_otp.plugins.otp_totp.models import TOTPDevice

    from apps.accounts.models import AuditLog
    from apps.core.models import Report
    a, b, t = pair
    services.send_text(t, b, 'грубость')
    client.force_login(a)
    client.post('/report/', {'ct': ContentType.objects.get_for_model(User).pk, 'id': b.pk, 'reason': 'abuse',
                             'thread': t.pk})
    r = Report.objects.get()
    assert r.thread_id == t.pk
    outsider_thread = Thread.objects.create()
    client.post('/report/', {'ct': ContentType.objects.get_for_model(User).pk, 'id': a.pk, 'reason': 'spam',
                             'thread': outsider_thread.pk})        # чужой диалог к жалобе не привяжется
    mod = User.objects.create_user('m', 'm@x.com', 'x', is_staff=True, is_superuser=True)
    dev = TOTPDevice.objects.create(user=mod, name='t', confirmed=True)
    client.force_login(mod)
    s = client.session
    s['otp_device_id'] = dev.persistent_id
    s.save()
    html = client.get(f'/moderation/chat/{r.pk}/').content.decode()
    assert 'грубость' in html
    assert AuditLog.objects.filter(user=mod, action='Модератор открыл переписку по жалобе').exists()
    client.force_login(b)
    assert client.get(f'/moderation/chat/{r.pk}/').status_code == 404


def test_message_str_does_not_leak_text(pair):
    a, _b, t = pair
    m = Message.objects.create(thread=t, sender=a, body='секрет')
    assert 'секрет' not in str(m)


# ---------- эмодзи звонка ----------

def _emoji_lists():
    web = (ROOT / 'static/js/call_emoji.js').read_text()
    app = (ROOT / 'mobile/src/lib/callEmoji.ts').read_text()
    web_list = json.loads(re.search(r'var EMOJI = (\[.*?\]);', web, re.DOTALL).group(1))
    app_list = json.loads(re.search(r'CALL_EMOJI: string\[\] = (\[.*?\]);', app, re.DOTALL).group(1))
    return web_list, app_list


def test_call_emoji_lists_match_on_site_and_app():
    web_list, app_list = _emoji_lists()
    assert web_list == app_list and len(set(web_list)) == 128


SDP_A = 'v=0\r\na=fingerprint:sha-256 AA:BB:CC:01\r\n'
SDP_B = 'v=0\r\na=fingerprint:sha-256 0F:1E:2D:3C\r\n'


def _reference_emoji():
    web_list, _ = _emoji_lists()
    a, b = 'AABBCC01', '0F1E2D3C'
    h = hashlib.sha256(('|'.join(sorted([a, b]))).encode()).digest()
    return [web_list[h[i] % 128] for i in range(4)]


@pytest.mark.skipif(not (shutil.which('node') or (Path.home() / '.local/node/bin/node').exists()),
                    reason='нет Node.js')
def test_call_emoji_same_for_both_sides():
    node = shutil.which('node') or str(Path.home() / '.local/node/bin/node')
    script = (f"globalThis.window=globalThis;{(ROOT / 'static/js/call_emoji.js').read_text()}"
              f"Promise.all([ilmCallEmoji({json.dumps(SDP_A)},{json.dumps(SDP_B)}),"
              f"ilmCallEmoji({json.dumps(SDP_B)},{json.dumps(SDP_A)})])"
              ".then(r=>console.log(JSON.stringify(r)))")
    out = json.loads(subprocess.run([node, '-e', script], capture_output=True, text=True, timeout=30, check=True).stdout)
    assert out[0] == out[1] == _reference_emoji()       # у звонящего и у отвечающего — одинаковые


# ---------- чаты по объявлениям, папки, поддержка ----------

def _listing(owner, title='Финики аджва', **kw):
    from apps.market.models import Category, Listing
    cat = Category.objects.first() or Category.objects.create(name='Еда', slug='food')
    return Listing.objects.create(title=title, description='-', price=28000, currency='UZS', category=cat, city='Ташкент',
                                  contact='-', owner=owner, status='approved', **kw)


def test_each_listing_has_its_own_chat_with_card(pair, client):
    a, b, personal = pair
    one, two = _listing(b), _listing(b, 'Мёд горный')
    t1 = services.open_direct(a, b, context=('buy', one.pk))
    t2 = services.open_direct(a, b, context=('buy', two.pk))
    assert len({personal.pk, t1.pk, t2.pk}) == 3                      # личный чат и два объявления — три разных
    assert services.open_direct(a, b, context=('buy', one.pk)).pk == t1.pk
    assert t1.folder == 'buy' and personal.folder == 'personal'
    info = services.thread_info(t1, a)
    assert info['card']['title'] == 'Финики аджва' and '28\xa0000' in info['card']['price'] and not info['card']['closed']
    assert 'предоплату' in info['notice']
    one.is_active = False
    one.save()
    assert services.thread_info(t1, a)['card']['closed'] is True       # объявление сняли — карточка это показывает
    client.force_login(a)
    html = client.get(f'/chat/{t1.pk}/').content.decode()
    assert 'ctxcard' in html and 'Финики аджва' in html and 'tg__folders' in html
    assert client.get('/chat/?f=buy').content.decode().count('<a class="tgrow') == 2


def test_context_must_belong_to_the_other_person(pair):
    a, b, personal = pair
    c = User.objects.create_user('c', 'c@x.com', 'x')
    foreign = _listing(c)
    assert services.open_direct(a, b, context=('buy', foreign.pk)).pk == personal.pk   # чужое объявление не подставить


def test_site_link_opens_listing_chat(pair, client):
    a, b, _t = pair
    item = _listing(b)
    client.force_login(a)
    r = client.get(f'/chat/start/?user={b.pk}&ctx=buy&ctx_id={item.pk}')
    t = Thread.objects.get(pk=int(r.url.strip('/').split('/')[-1]))
    assert (t.context_type, t.context_id, t.subject) == ('buy', item.pk, 'Финики аджва')


def test_prepayment_request_is_flagged_only_in_market_chats(pair):
    a, b, personal = pair
    t = services.open_direct(a, b, context=('buy', _listing(b).pk))
    assert services.send_text(t, b, 'Переведите предоплату на карту 8600 1234 5678 9012')['warn'] is True
    assert services.send_text(t, b, 'Ассаляму алейкум, ещё продаётся')['warn'] is False
    assert services.send_text(personal, b, 'скинь предоплату')['warn'] is False


def test_support_chat(pair, client):
    from apps.core.models import SiteSettings
    a, _b, _t = pair
    with pytest.raises(services.ChatError):
        services.open_support(a)
    helper = User.objects.create_user('help', 'help@x.com', 'x', is_staff=True)
    SiteSettings.objects.update(support_user=helper)
    t = services.open_support(a)
    assert t.folder == 'support' and services.open_support(a).pk == t.pk
    assert 'командой ilm4' in services.thread_info(t, a)['notice']


def test_nikah_chat_goes_to_nikah_folder():
    from apps.nikah import services as nikah
    from apps.nikah.tests.test_nikah import make_profile
    b, s = make_profile('nb@x.com', 'M'), make_profile('ns@x.com', 'F')
    nikah.send_interest(b, s)
    m = nikah.send_interest(s, b)
    assert m.thread.folder == 'nikah' and m.thread.context_id == m.pk


# ---------- «отправить файлом» и сжатие видео ----------

def test_send_as_file_keeps_original_and_downloads(pair, settings, tmp_path, client):
    settings.MEDIA_ROOT = tmp_path
    a, b, t = pair
    data = os.urandom(150_000)
    client.force_login(a)
    r = client.post(f'/chat/{t.pk}/upload/', {'kind': 'file', 'file': SimpleUploadedFile('Договор №5.pdf', data)})
    assert r.status_code == 200, r.content
    p = r.json()
    assert p['kind'] == 'file' and p['file_name'] == 'Договор №5.pdf' and p['file_size'] == len(data)
    m = Message.objects.get(pk=p['id'])
    assert 'Договор' not in m.attachment.name and 'Договор' not in m.meta_enc      # имя файла тоже зашифровано
    client.force_login(b)
    got = client.get(f'/chat/file/{m.pk}/')
    assert b''.join(got.streaming_content) == data                                  # без сжатия, байт в байт
    assert got['Content-Disposition'].startswith('attachment') and got['Content-Type'] == 'application/octet-stream'


def test_programs_are_sent_but_marked_risky(pair, settings, tmp_path, client):
    """Как в Telegram: программы и скрипты отправляются, но получатель видит предупреждение,
    а сайт отдаёт файл только на скачивание."""
    settings.MEDIA_ROOT = tmp_path
    a, b, t = pair
    client.force_login(a)
    r = client.post(f'/chat/{t.pk}/upload/', {'kind': 'file', 'file': SimpleUploadedFile('tool.apk', b'PK..')})
    assert r.status_code == 200 and r.json()['file_risky'] is True
    r2 = client.post(f'/chat/{t.pk}/upload/', {'kind': 'file', 'file': SimpleUploadedFile('notes.txt', b'hello')})
    assert r2.json()['file_risky'] is False
    client.force_login(b)
    page = client.get(f'/chat/{t.pk}/').content.decode()
    assert page.count('bub__risk') == 1
    got = client.get(f"/chat/file/{r.json()['id']}/")
    assert got['Content-Disposition'].startswith('attachment') and got['X-Content-Type-Options'] == 'nosniff'


def _send_parts(client, base, t, data, name='big.bin', kind='file', part=None, **extra):
    r = client.post(f'{base}/{t.pk}/upload/begin/', {'kind': kind, 'name': name, 'size': len(data), **extra})
    assert r.status_code == 200, r.content
    up, size = r.json()['upload'], part or r.json()['part']
    for off in range(0, len(data), size):
        r = client.post(f'{base}/upload/{up}/part/?offset={off}', data[off:off + size],
                        content_type='application/octet-stream')
        assert r.status_code == 200, r.content
    return up


def test_big_file_goes_in_parts_and_survives_a_dropped_connection(pair, settings, tmp_path, client):
    """Файл больше одного запроса: части по 4 МБ шифруются сразу, обрыв — продолжение с того же места."""
    settings.MEDIA_ROOT = tmp_path
    a, b, t = pair
    data = os.urandom(services.PART * 2 + 70_000)                 # три части, последняя неполная
    client.force_login(a)
    r = client.post(f'/chat/{t.pk}/upload/begin/', {'kind': 'file', 'name': 'Фильм.mkv', 'size': len(data)})
    up, part = r.json()['upload'], r.json()['part']
    assert part == services.PART
    assert client.post(f'/chat/upload/{up}/part/?offset=0', data[:part], content_type='application/octet-stream').status_code == 200
    # часть «потерялась» и пришла не та: сервер говорит, с какого места продолжать
    skip = client.post(f'/chat/upload/{up}/part/?offset={part * 2}', data[part * 2:], content_type='application/octet-stream')
    assert skip.status_code == 409 and skip.json()['received'] == part
    assert client.get(f'/chat/upload/{up}/').json()['received'] == part
    early = client.post(f'/chat/upload/{up}/finish/')
    assert early.status_code == 409 and not Message.objects.filter(kind='file').exists()
    for off in (part, part * 2):
        client.post(f'/chat/upload/{up}/part/?offset={off}', data[off:off + part], content_type='application/octet-stream')
    tmp_file = next((tmp_path / 'chat' / 'tmp').iterdir())
    assert data[:64] not in tmp_file.read_bytes()                  # на диске — только зашифрованное
    done = client.post(f'/chat/upload/{up}/finish/')
    assert done.status_code == 200, done.content
    p = done.json()
    assert p['file_name'] == 'Фильм.mkv' and p['file_size'] == len(data)
    assert not list((tmp_path / 'chat' / 'tmp').iterdir())
    client.force_login(b)
    got = client.get(f"/chat/file/{p['id']}/")
    assert hashlib.sha256(b''.join(got.streaming_content)).digest() == hashlib.sha256(data).digest()
    tail = client.get(f"/chat/file/{p['id']}/", HTTP_RANGE=f'bytes={len(data) - 10}-')
    assert b''.join(tail.streaming_content) == data[-10:]


def test_big_upload_rules(pair, settings, tmp_path, client):
    """Чужую загрузку не тронуть, предел размера и дневной лимит работают, брошенное удаляется."""
    from django.core.cache import cache

    from apps.chat.models import Upload
    from apps.core.models import SiteSettings
    settings.MEDIA_ROOT = tmp_path
    cache.clear()
    a, b, t = pair
    client.force_login(a)
    st = SiteSettings.get_solo()
    st.chat_file_max_mb, st.chat_daily_upload_mb = 1, 1
    st.save()
    assert client.post(f'/chat/{t.pk}/upload/begin/', {'kind': 'file', 'name': 'x', 'size': 5_000_000}).status_code == 400
    data = os.urandom(700_000)
    up = _send_parts(client, '/chat', t, data)
    client.force_login(b)
    assert client.post(f'/chat/upload/{up}/finish/').status_code == 404              # чужая загрузка
    assert client.post(f'/chat/upload/{up}/cancel/').status_code == 404
    client.force_login(a)
    assert client.post(f'/chat/upload/{up}/finish/').status_code == 200
    again = client.post(f'/chat/{t.pk}/upload/begin/', {'kind': 'file', 'name': 'y', 'size': 700_000})
    assert again.status_code == 429                                                  # 0.7 + 0.7 МБ > 1 МБ в сутки
    cache.clear()
    left = client.post(f'/chat/{t.pk}/upload/begin/', {'kind': 'file', 'name': 'z', 'size': 700_000}).json()['upload']
    Upload.objects.filter(pk=left).update(created_at=timezone.now() - timedelta(hours=30))
    assert services.purge_uploads() == 1
    assert not Upload.objects.exists() and not list((tmp_path / 'chat' / 'tmp').iterdir())


def test_big_upload_from_app_api(pair, settings, tmp_path, client):
    from apps.api.models import ApiToken
    settings.MEDIA_ROOT = tmp_path
    a, _b, t = pair
    auth = {'HTTP_AUTHORIZATION': 'Bearer ' + ApiToken.issue(a)}
    data = os.urandom(200_000)
    r = client.post(f'/api/v1/chat/{t.pk}/upload/begin/', json.dumps({'kind': 'file', 'name': 'a.zip', 'size': len(data),
                                                                    'silent': True}),
                    content_type='application/json', **auth)
    assert r.status_code == 200, r.content
    up = r.json()['upload']
    assert client.post(f'/api/v1/chat/upload/{up}/part/?offset=0', data, content_type='application/octet-stream',
                       **auth).status_code == 200
    done = client.post(f'/api/v1/chat/upload/{up}/finish/', **auth)
    assert done.status_code == 200, done.content
    assert done.json()['file_name'] == 'a.zip' and done.json()['mine'] is True and done.json()['silent'] is True
    got = client.get(f"/api/v1/chat/file/{done.json()['id']}/", **auth)
    assert b''.join(got.streaming_content) == data


def test_video_is_compressed_like_telegram(pair, settings, tmp_path):
    from apps.chat import transcode
    from apps.chat.filecrypt import Reader
    exe = transcode.ffmpeg_path()
    if not exe:
        pytest.skip('нет ffmpeg')
    settings.MEDIA_ROOT = tmp_path
    a, _b, t = pair
    src = tmp_path / 'big.mp4'                    # 2 секунды 1080p с высоким битрейтом
    subprocess.run([exe, '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=1920x1080:rate=30', '-f', 'lavfi',
                    '-i', 'sine=frequency=440', '-t', '2', '-c:v', 'libx264', '-b:v', '12M', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', str(src)], check=True, timeout=120)
    raw = src.read_bytes()
    p = services.store_upload(t, a, 'video', SimpleUploadedFile('big.mp4', raw, content_type='video/mp4'), duration=2)
    assert transcode.compress(p['id']) is True
    m = Message.objects.get(pk=p['id'])
    out = tmp_path / 'check.mp4'
    with m.attachment.open('rb') as fh:
        reader = Reader(t.pk, fh, os.path.getsize(m.attachment.path))
        out.write_bytes(b''.join(reader.iter_range(0, reader.size - 1)))
    info = transcode.probe(str(out))
    assert info['height'] == 720 and info['width'] == 1280              # 1080p → 720p
    assert out.stat().st_size < len(raw) / 2                             # и заметно меньше
    assert len(list((tmp_path / 'chat').rglob('*.enc'))) == 1            # несжатый исходник удалён
