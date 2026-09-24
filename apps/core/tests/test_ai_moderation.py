"""ИИ-модерация: вердикт Claude сохраняется, «чисто» одобряется (если включено), контакты — без ИИ."""
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.core.models import AIReview, Moderation, SiteSettings
from apps.jobs.models import Vacancy

User = get_user_model()
pytestmark = pytest.mark.django_db
VAC = {'title': 'Повар', 'category': 'other', 'company': 'Кафе', 'city': 'Ташкент', 'description': 'Кухня',
       'contact': '@hr'}


class FakeResp:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass

    def json(self):
        return {'content': [{'type': 'text', 'text': self.text}]}


@pytest.fixture
def claude(monkeypatch, settings):
    settings.ANTHROPIC_API_KEY = 'sk-test'
    answers = []
    monkeypatch.setattr('apps.core.ai_moderation.requests.post',
                        lambda *a, **k: FakeResp(answers.pop(0) if answers else '{"verdict": "ok", "reasons": []}'))
    return answers


def test_verdict_saved_and_auto_approve(claude):
    st = SiteSettings.get_solo()
    st.ai_auto_approve = True
    st.save()
    owner = User.objects.create_user('o', 'o@x.com', 'x')
    good = Vacancy.objects.create(owner=owner, **VAC)
    bad = Vacancy.objects.create(owner=owner, **{**VAC, 'title': 'Продаю вино'})
    claude.extend(['{"verdict": "ok", "reasons": []}',
                   'Вот ответ: {"verdict": "reject", "reasons": ["алкоголь — харам"]}'])
    call_command('ai_moderate')
    good.refresh_from_db()
    bad.refresh_from_db()
    assert good.status == Moderation.APPROVED
    assert bad.status == Moderation.PENDING
    assert AIReview.objects.get(object_id=bad.pk).reasons == ['алкоголь — харам']


def test_not_rechecked_until_changed(claude):
    owner = User.objects.create_user('o', 'o@x.com', 'x')
    v = Vacancy.objects.create(owner=owner, **VAC)
    call_command('ai_moderate')
    first = AIReview.objects.get(object_id=v.pk).checked_at
    call_command('ai_moderate')
    assert AIReview.objects.get(object_id=v.pk).checked_at == first     # не менялось — не тратим запрос
    Vacancy.objects.filter(pk=v.pk).update(description='Новая кухня')
    call_command('ai_moderate')
    assert AIReview.objects.get(object_id=v.pk).checked_at > first


def test_nikah_contacts_rejected_without_ai(claude):
    from apps.nikah.tests.test_nikah import make_profile
    p = make_profile('n@x.com', 'M', status=Moderation.PENDING, about='пишите в телеграм @ahmad_uz')
    call_command('ai_moderate')
    r = AIReview.objects.get(object_id=p.pk, content_type__model='nikahprofile')
    assert r.verdict == 'reject' and r.model_name == 'regex'


def test_disabled_without_key(settings):
    settings.ANTHROPIC_API_KEY = settings.OPENAI_API_KEY = ''
    User.objects.create_user('o', 'o@x.com', 'x')
    call_command('ai_moderate')
    assert not AIReview.objects.exists()


def test_nikah_chat_blocks_contacts(client):
    from apps.nikah import services
    from apps.nikah.tests.test_nikah import make_profile
    b = make_profile('b@x.com', 'M')
    s = make_profile('s@x.com', 'F')
    services.send_interest(b, s)
    m = services.send_interest(s, b)
    client.force_login(b.user)
    client.post(f'/chat/{m.thread_id}/', {'body': 'мой номер +998 90 123 45 67'})
    client.post(f'/chat/{m.thread_id}/', {'body': 'Ассаляму алейкум! Как ваши дела?'})
    bodies = list(m.thread.messages.exclude(kind='system').values_list('body', flat=True))
    assert bodies == ['Ассаляму алейкум! Как ваши дела?']
