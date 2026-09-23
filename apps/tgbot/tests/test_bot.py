"""Telegram-бот: /start, модерация кнопками (только модераторы), верификация кружком, бонус за приглашение."""
import pytest
from django.contrib.auth import get_user_model

from apps.core.models import Moderation
from apps.nikah.models import NikahProfile
from apps.nikah.tests.test_nikah import make_profile
from apps.tgbot.dispatch import handle_update

User = get_user_model()
pytestmark = pytest.mark.django_db
MOD_CHAT = '-100777'


@pytest.fixture
def sent(monkeypatch, settings):
    """Перехват вызовов Bot API: список (method, data)."""
    settings.TELEGRAM_BOT_TOKEN = '1:T'
    settings.TELEGRAM_MODERATION_CHAT_ID = MOD_CHAT
    settings.SITE_URL = 'https://ilm4.test'
    calls = []

    def fake(method, data=None, files=None, timeout=10):
        calls.append((method, data or {}))
        return {'message_id': 1} if method != 'createInvoiceLink' else 'https://t.me/$inv'
    for mod in ('apps.tgbot.dispatch', 'apps.nikah.bot', 'apps.payments.stars', 'apps.accounts.telegram'):
        monkeypatch.setattr(f'{mod}.api', fake, raising=False)
    monkeypatch.setattr('apps.accounts.telegram.send_message', lambda *a, **k: True)
    return calls


def _cb(data, chat=MOD_CHAT, uid=5):
    return {'update_id': 1, 'callback_query': {'id': 'q', 'data': data, 'from': {'id': uid, 'username': 'mod'},
                                              'message': {'chat': {'id': int(chat)}, 'message_id': 9, 'text': 'анкета'}}}


def test_start_sends_open_button(sent):
    handle_update({'update_id': 1, 'message': {'message_id': 1, 'chat': {'id': 42, 'type': 'private'},
                                                'from': {'id': 42}, 'text': '/start'}})
    method, data = sent[-1]
    assert method == 'sendMessage' and data['reply_markup']['inline_keyboard'][0][0]['web_app']['url'] == \
        'https://ilm4.test/nikah/'


def test_moderation_approve_only_from_mod_chat(sent):
    p = make_profile('p@x.com', 'F', status=Moderation.PENDING)
    handle_update(_cb(f'nk:mod:ok:{p.pk}', chat='-100999'))        # чужой чат — нельзя
    assert NikahProfile.objects.get(pk=p.pk).status == Moderation.PENDING
    handle_update(_cb(f'nk:mod:ok:{p.pk}'))
    assert NikahProfile.objects.get(pk=p.pk).status == Moderation.APPROVED


def test_moderator_id_whitelist(sent, settings):
    settings.TELEGRAM_MODERATOR_IDS = [1001]
    p = make_profile('p@x.com', 'F', status=Moderation.PENDING)
    handle_update(_cb(f'nk:mod:ok:{p.pk}', uid=5))
    assert NikahProfile.objects.get(pk=p.pk).status == Moderation.PENDING
    handle_update(_cb(f'nk:mod:ok:{p.pk}', uid=1001))
    assert NikahProfile.objects.get(pk=p.pk).status == Moderation.APPROVED


def test_referral_bonus_on_approve(sent):
    ref = make_profile('r@x.com', 'M')
    p = make_profile('p@x.com', 'F', status=Moderation.PENDING, referred_by=ref)
    handle_update(_cb(f'nk:mod:ok:{p.pk}'))
    handle_update(_cb(f'nk:mod:ok:{p.pk}'))       # повторное нажатие бонус не удваивает
    ref.refresh_from_db()
    assert ref.is_premium
    days = (ref.premium_until - p.created_at).days
    assert 2 <= days <= 3


def test_video_note_goes_to_moderators_and_verifies(sent):
    p = make_profile('p@x.com', 'M')
    p.user.telegram_id = 555
    p.user.save()
    handle_update({'update_id': 2, 'message': {'message_id': 77, 'chat': {'id': 555, 'type': 'private'},
                                                'from': {'id': 555}, 'video_note': {'file_id': 'F'}}})
    methods = [m for m, _d in sent]
    assert 'copyMessage' in methods
    copy = next(d for m, d in sent if m == 'copyMessage')
    assert copy['chat_id'] == MOD_CHAT and copy['from_chat_id'] == 555
    handle_update(_cb(f'nk:ver:ok:{p.pk}'))
    assert NikahProfile.objects.get(pk=p.pk).verified


def test_webhook_requires_secret(client, settings, sent):
    settings.TELEGRAM_WEBHOOK_SECRET = 's3cret'
    body = '{"update_id": 1}'
    assert client.post('/tg/webhook/', body, content_type='application/json').status_code == 403
    assert client.post('/tg/webhook/', body, content_type='application/json',
                       HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='s3cret').status_code == 200
