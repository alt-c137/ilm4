"""Фаза 8 — чат: диалоги, доступ, WebSocket, уведомления."""
import pytest
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model

from apps.chat.models import Message, Thread
from apps.core.models import Notification

User = get_user_model()
pytestmark = pytest.mark.django_db


def make_thread():
    alice = User.objects.create_user('alice', 'alice@x.com', 'x')
    bob = User.objects.create_user('bob', 'bob@x.com', 'x')
    thread = Thread.objects.create(subject='iPhone 14 Pro')
    thread.participants.add(alice, bob)
    return alice, bob, thread


def test_start_thread_by_email(client):
    alice = User.objects.create_user('alice', 'alice@x.com', 'x')
    User.objects.create_user('bob', 'bob@x.com', 'x')
    client.force_login(alice)
    response = client.post('/chat/start/', {'email': 'bob@x.com'})
    assert response.status_code == 302
    assert Thread.objects.count() == 1
    # повторный старт — тот же диалог
    client.post('/chat/start/', {'email': 'bob@x.com'})
    assert Thread.objects.count() == 1


def test_message_via_form_and_access(client):
    alice, _bob, thread = make_thread()
    client.force_login(alice)
    client.post(f'/chat/{thread.pk}/', {'body': 'Здравствуйте! Ещё продаёте?'})
    assert any(m.body == 'Здравствуйте! Ещё продаёте?' for m in Message.objects.all())

    # чужой диалог — редирект в ящик, содержимое не показывается
    mallory = User.objects.create_user('m', 'm@x.com', 'x')
    client.force_login(mallory)
    response = client.get(f'/chat/{thread.pk}/')
    assert response.status_code == 302
    assert 'Здравствуйте' not in client.get(f'/chat/{thread.pk}/', follow=True).content.decode()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)  # sync_to_async пишет вне тест-транзакции
async def test_websocket_chat_delivers_and_notifies():
    from channels.db import database_sync_to_async

    from config.asgi import application

    alice, bob, thread = await database_sync_to_async(make_thread)()
    comm_alice = WebsocketCommunicator(application, f'/ws/chat/{thread.pk}/')
    comm_bob = WebsocketCommunicator(application, f'/ws/chat/{thread.pk}/')
    comm_alice.scope['user'] = alice
    comm_bob.scope['user'] = bob

    assert await comm_alice.connect()
    assert await comm_bob.connect()

    await comm_alice.send_json_to({'body': 'Ассаляму алейкум!'})
    event_a = await comm_alice.receive_json_from()
    event_b = await comm_bob.receive_json_from()
    assert event_a['body'] == event_b['body'] == 'Ассаляму алейкум!'
    assert event_a['sender_id'] == alice.id

    await comm_alice.disconnect()
    await comm_bob.disconnect()

    # проверка сохранения и уведомления — ORM только через sync_to_async
    saved = await database_sync_to_async(
        lambda: Message.objects.filter(thread=thread, sender=alice).exists())()
    notified = await database_sync_to_async(
        lambda: Notification.objects.filter(user=bob, read=False).exists())()
    assert saved
    assert notified  # колокольчик получил


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_websocket_denies_stranger():
    from channels.db import database_sync_to_async

    from config.asgi import application

    _, _, thread = await database_sync_to_async(make_thread)()
    stranger = await database_sync_to_async(User.objects.create_user)(
        'stranger', 'str@x.com', 'x')
    comm = WebsocketCommunicator(application, f'/ws/chat/{thread.pk}/')
    comm.scope['user'] = stranger
    connected, _ = await comm.connect()
    assert not connected  # не участник — соединение закрыто


@pytest.mark.django_db
def test_message_body_encrypted_at_rest():
    """В БД — шифр, в коде — открытый текст."""
    from django.contrib.auth import get_user_model
    from django.db import connection

    from apps.chat.models import Message, Thread

    U = get_user_model()
    a = U.objects.create_user('enc_a', 'ea@x.com', 'pass12345')
    t = Thread.objects.create()
    t.participants.add(a)
    m = Message.objects.create(thread=t, sender=a, body='Секретный текст')
    with connection.cursor() as c:
        c.execute('select body from chat_message where id = %s', [m.pk])
        raw = c.fetchone()[0]
    assert raw.startswith('enc1:') and 'Секретный' not in raw
    assert Message.objects.get(pk=m.pk).body == 'Секретный текст'


@pytest.fixture
def pair(db):
    from django.contrib.auth import get_user_model

    from apps.chat.models import Thread
    from apps.core.models import ModuleConfig
    ModuleConfig.objects.update_or_create(key='chat', defaults={'name': 'Чат', 'status': 'on'})
    U = get_user_model()
    a = U.objects.create_user('ma', 'ma@x.com', 'pass12345')
    b = U.objects.create_user('mb', 'mb@x.com', 'pass12345')
    t = Thread.objects.create()
    t.participants.add(a, b)
    return a, b, t


def _jpeg():
    import io

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (40, 30), (200, 10, 10)).save(buf, 'JPEG')
    return SimpleUploadedFile('p.jpg', buf.getvalue(), content_type='image/jpeg')


def test_photo_upload_and_private_access(client, pair, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    from django.contrib.auth import get_user_model

    from apps.chat.models import Message
    a, _b, t = pair
    client.force_login(a)
    r = client.post(f'/chat/{t.pk}/upload/', {'kind': 'photo', 'file': _jpeg()})
    assert r.status_code == 200, r.content
    m = Message.objects.get(pk=r.json()['id'])
    assert m.kind == 'photo' and m.attachment.name.endswith('.jpg')
    assert client.get(f'/chat/file/{m.pk}/').status_code == 200          # участник
    stranger = get_user_model().objects.create_user('st', 'st@x.com', 'pass12345')
    client.force_login(stranger)
    assert client.get(f'/chat/file/{m.pk}/').status_code == 404          # посторонний — нет


def test_disabled_feature_rejected(client, pair, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    from apps.core.models import SiteSettings
    s = SiteSettings.get_solo()
    s.chat_photos_enabled = False
    s.save()
    a, _b, t = pair
    client.force_login(a)
    assert client.post(f'/chat/{t.pk}/upload/', {'kind': 'photo', 'file': _jpeg()}).status_code == 403


def test_voice_rejects_fake_file(client, pair, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    from django.core.files.uploadedfile import SimpleUploadedFile
    a, _b, t = pair
    client.force_login(a)
    fake = SimpleUploadedFile('v.webm', b'<script>alert(1)</script>', content_type='audio/webm')
    assert client.post(f'/chat/{t.pk}/upload/', {'kind': 'voice', 'file': fake}).status_code == 400
