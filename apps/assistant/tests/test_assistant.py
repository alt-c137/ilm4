"""ИИ-помощник: свой ключ (зашифрован), поставщики (Claude и OpenAI-совместимые), лимит и подписка на ключе площадки,
цикл «модель → действие → ответ» на подменённом клиенте, действия от имени человека, сводка дня, чтение сообщений по разрешению."""
from types import SimpleNamespace
from unittest import mock

import pytest
from django.contrib.auth import get_user_model

from apps.assistant import services, tools
from apps.assistant.models import AssistantKey, AssistantPlan, Chat, Turn
from apps.core.models import ModuleConfig, SiteSettings
from apps.tracker.models import Habit

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def user(settings):
    settings.ANTHROPIC_API_KEY = ''
    settings.ASSISTANT_API_KEY = ''
    for key in ('assistant', 'tracker', 'map', 'chat'):
        ModuleConfig.objects.update_or_create(key=key, defaults={'name': key, 'status': 'on'})
    return User.objects.create_user('ai', 'ai@x.com', 'x', first_name='Али')


class FakeResp:
    def __init__(self, content, stop):
        self._content, self.stop_reason = content, stop

    def to_dict(self):
        return {'content': self._content}


def fake_client(*responses):
    seq = list(responses)
    sent = []

    def create(**kw):
        sent.append(kw)
        return seq.pop(0)
    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    return client, sent


def test_own_key_is_encrypted_and_validated(user):
    with pytest.raises(services.AssistantError):
        services.set_key(user, 'not-a-key')
    services.set_key(user, 'sk-ant-api03-' + 'x' * 40)
    row = AssistantKey.objects.get(user=user)
    assert 'sk-ant' not in row.key_enc and row.hint == '…xxxx'
    assert services._own_key(row).startswith('sk-ant-api03-')
    assert services.state(user)['ready'] and services.state(user)['provider'] == 'anthropic'
    services.set_key(user, '')
    assert not services.state(user)['own_key'] and not services.state(user)['ready']


def test_needs_site_key_or_own_key(user, settings):
    with pytest.raises(services.AssistantError):
        services.send(user, 'привет')
    settings.ANTHROPIC_API_KEY = 'sk-ant-site'
    st = SiteSettings.get_solo()
    st.assistant_daily_free = 1
    st.save()
    assert services.state(user)['left'] == 1


def test_tool_loop_adds_habit_and_answers(user):
    first = FakeResp([{'type': 'tool_use', 'id': 't1', 'name': 'add_habit',
                       'input': {'title': 'Коран', 'target': 5, 'unit': 'страниц', 'reminders': '06:00'}}], 'tool_use')
    final = FakeResp([{'type': 'text', 'text': 'Готово: добавил «Коран», 5 страниц, напомню в 06:00.'}], 'end_turn')
    client, sent = fake_client(first, final)
    services.set_key(user, 'sk-ant-api03-' + 'y' * 40)
    with mock.patch.object(services, '_client', return_value=client):
        out = services.send(user, 'Добавь привычку: Коран 5 страниц, напоминание в 6 утра')
    h = Habit.objects.get(owner=user)
    assert h.title == 'Коран' and h.target == 5 and h.times() == ['06:00']
    assert [m['role'] for m in out['messages']] == ['user', 'action', 'assistant']
    assert out['actions'] == ['Добавил привычку в трекер'] and h.emoji == 'h-check'
    # второй запрос к модели получил результат действия, и история только дописывается
    assert sent[1]['messages'][-1]['content'][0]['type'] == 'tool_result'
    assert sent[0]['model'] == 'claude-opus-5-5' and sent[0]['fallbacks'] == 'default'
    assert Turn.objects.filter(chat_id=out['chat']).count() == 4


def test_refusal_is_handled(user):
    services.set_key(user, 'sk-ant-api03-' + 'y' * 40)
    client, _sent = fake_client(FakeResp([], 'refusal'))
    with mock.patch.object(services, '_client', return_value=client):
        out = services.send(user, '…')
    assert out['messages'][-1]['role'] == 'assistant'


def test_tools_act_only_for_this_user(user):
    other = User.objects.create_user('o', 'o@x.com', 'x')
    from apps.tracker import services as tr
    foreign = tr.create_habit(other, {'title': 'Чужая'})
    res, err = tools.run(user, 'mark_habit', {'habit_id': foreign.pk})
    assert err and 'error' in res
    res, err = tools.run(user, 'schedule_meeting', {'title': 'Забрать справку', 'date': '2999-01-01', 'time': '15:00'})
    assert not err and Habit.objects.get(pk=res['habit_id']).once_on.year == 2999
    res, err = tools.run(user, 'prayer_times', {'city': 'Ташкент'})
    assert not err and set(res['times']) >= {'fajr', 'maghrib'}
    res, err = tools.run(user, 'find_places', {'category': 'mosque'})
    assert not err and res['items'] == []
    res, err = tools.run(user, 'nope', {})
    assert err


def test_site_page(user, client):
    client.force_login(user)
    page = client.get('/assistant/').content.decode()
    assert 'ИИ-помощник' in page and 'Свой ИИ' in page and 'jv__orb' in page and 'OpenAI' in page      # сводка дня есть и без ключа


def test_openai_compatible_provider(user):
    """Свой ключ OpenAI / Z.AI: тот же цикл действий, другой вид истории; адрес сервера — только из списка."""
    with pytest.raises(services.AssistantError):
        services.set_key(user, 'sk-' + 'k' * 40, 'custom', 'my-model', 'https://169.254.169.254/v1')     # чужой адрес — нельзя
    with pytest.raises(services.AssistantError):
        services.set_key(user, 'sk-' + 'k' * 40, 'openai', 'bad model name!')
    services.set_key(user, 'sk-' + 'k' * 40, 'zai', '')
    st = services.state(user)
    assert st['provider'] == 'zai' and st['model'] == 'glm-5.3' and st['ready']
    replies = [
        {'choices': [{'message': {'role': 'assistant', 'content': None, 'reasoning_content': 'думаю…', 'tool_calls': [
            {'id': 'c1', 'type': 'function', 'function': {'name': 'schedule_meeting',
                                                         'arguments': '{"title": "Забрать справку", "date": "2999-01-01", "time": "15:00"}'}}]}}]},
        {'choices': [{'message': {'role': 'assistant', 'content': 'Поставил встречу на 1 января в 15:00.'}}]},
    ]
    sent = []

    def post(cfg, payload):
        sent.append((cfg, payload))
        return replies.pop(0)
    with mock.patch.object(services, '_post_openai', side_effect=post):
        out = services.send(user, 'Поставь встречу: забрать справку 1 января 2999 в 15:00')
    assert Habit.objects.get(owner=user).once_on.year == 2999
    assert [m['role'] for m in out['messages']] == ['user', 'action', 'assistant'] and out['actions'] == ['Поставил в трекер']
    cfg, first = sent[0]
    assert cfg['base'] == 'https://api.z.ai/api/paas/v4' and first['model'] == 'glm-5.3' and first['messages'][0]['role'] == 'system'
    assert first['tools'][0]['type'] == 'function'
    second = sent[1][1]['messages']
    assert second[-1]['role'] == 'tool' and second[-1]['tool_call_id'] == 'c1' and 'reasoning_content' not in second[-2]
    assert Chat.objects.get(pk=out['chat']).api == 'openai'
    # сменили поставщика на Claude — старый разговор не продолжаем (другой формат истории)
    services.set_key(user, 'sk-ant-api03-' + 'y' * 40, 'anthropic')
    client, _sent = fake_client(FakeResp([{'type': 'text', 'text': 'Ва алейкум ассалям'}], 'end_turn'))
    with mock.patch.object(services, '_client', return_value=client):
        again = services.send(user, 'Ассаляму алейкум', out['chat'])
    assert again['chat'] != out['chat']


def test_plan_removes_daily_limit(user, settings):
    from datetime import timedelta

    from django.utils import timezone
    settings.ANTHROPIC_API_KEY = 'sk-ant-site'
    st = SiteSettings.get_solo()
    st.assistant_daily_free = 0
    st.save()
    assert not services.state(user)['ready']
    AssistantPlan.objects.create(user=user, until=timezone.localdate() + timedelta(days=30))
    assert services.state(user)['ready'] and services.state(user)['unlimited']


def test_briefing_and_reading_messages_by_permission(user):
    from apps.chat import services as chat
    friend = User.objects.create_user('f', 'f@x.com', 'x', first_name='Умар')
    thread = chat.open_direct(friend, user)
    chat.send_text(thread, friend, 'Завтра в 10 у мечети?')
    secret = chat.open_private_thread([friend, user], subject='Никях', context=('nikah', 1))
    chat.send_text(secret, friend, 'личное')
    tools.run(user, 'schedule_meeting', {'title': 'Забрать справку', 'date': '2999-01-01'})
    brief = services.briefing(user)
    assert brief['prayer']['time'] and brief['unread'] == 2 and brief['tracker']['total'] == 0
    assert 'Умар' in [c['name'] for c in brief['chats']]
    assert 'recent_messages' not in [t['name'] for t in tools.for_user(False)]
    res, err = tools.run(user, 'recent_messages', {})
    assert err                                                    # без разрешения помощник тексты не получает
    services.set_prefs(user, True)
    assert services.state(user)['read_chats'] and 'recent_messages' in [t['name'] for t in tools.for_user(True)]
    res, err = tools.run(user, 'recent_messages', {}, read_chats=True)
    texts = [m['text'] for m in res['items']]
    assert not err and texts == ['Завтра в 10 у мечети?']        # чат никяха не передаётся никогда
