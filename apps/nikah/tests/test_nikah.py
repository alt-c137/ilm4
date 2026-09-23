"""Никях v2: мастер анкеты, лента без фото, взаимный интерес, обмен фото, чат, Telegram."""
import hashlib
import hmac
import io
import json
import time
from datetime import timedelta
from urllib.parse import urlencode

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from apps.core.models import Moderation, SiteSettings
from apps.nikah import services
from apps.nikah.models import NikahInterest, NikahMatch, NikahProfile
from apps.wallet import services as wallet
from apps.wallet.models import Transaction

User = get_user_model()
pytestmark = pytest.mark.django_db


def png(color='green'):
    buf = io.BytesIO()
    Image.new('RGB', (60, 80), color).save(buf, 'PNG')
    return SimpleUploadedFile('me.png', buf.getvalue(), content_type='image/png')


def wizard_data(gender='M', **over):
    data = {
        'gender': gender, 'name': 'Ахмад' if gender == 'M' else 'Марьям', 'age': '27',
        'age_from': '20', 'age_to': '35', 'country': 'Узбекистан', 'city': 'Ташкент', 'nationality': 'узбек',
        'height': '178', 'weight': '75', 'marital': 'never', 'wife_number': '1', 'polygyny': 'no',
        'madhhab': 'hanafi', 'aqida': 'athari', 'prayer': 'five', 'quran': 'daily', 'where_allah': 'above',
        'has_children': 'no', 'children_want': 'yes', 'children_accept': 'discuss', 'ready_when': 'soon',
        'look': 'full' if gender == 'M' else 'hijab',
        'manhaj_text': 'Следую Корану и Сунне по пониманию саляфов, слушаю уроки учёных.',
        'about': 'Работаю инженером, учу арабский, люблю спокойную семейную жизнь.',
        'partner_expectations': 'Богобоязненная, соблюдающая, с желанием учиться и растить детей.',
        'photo_mode': 'none',
        **{f'faith_{k}': 'yes' for k in ('prayer', 'quran', 'fast', 'halal', 'ready', 'serious')},
        'faith_relations': 'no',
        **{f'agree_{k}': '1' for k in ('truth', 'nikah', 'privacy', 'contacts', 'rules')},
    }
    data.update(over)
    return data


def make_profile(email, gender, status=Moderation.APPROVED, **fields):
    user = User.objects.create_user(email.split('@')[0], email, 'x')
    base = {'gender': gender, 'name': 'Имя', 'age': 27, 'age_from': 20, 'age_to': 40, 'country': 'Узбекистан',
            'city': 'Ташкент', 'marital': 'never', 'madhhab': 'hanafi', 'aqida': 'athari', 'prayer': 'five',
            'quran': 'daily', 'where_allah': 'above', 'has_children': 'no', 'children_want': 'yes', 'children_accept': 'discuss',
            'ready_when': 'soon', 'look': 'full' if gender == 'M' else 'hijab', 'relocation': 'country',
            'manhaj_text': 'Коран и Сунна', 'about': 'о себе достаточно подробно',
            'partner_expectations': 'ищу богобоязненного супруга', 'photo_mode': 'none', 'status': status}
    base.update(fields)
    return NikahProfile.objects.create(user=user, **base)


# ---------- мастер анкеты ----------

def test_wizard_creates_pending_profile(client):
    user = User.objects.create_user('w', 'w@x.com', 'x')
    client.force_login(user)
    resp = client.post('/nikah/create/', wizard_data(relocation='abroad'))
    assert resp.status_code == 302
    p = NikahProfile.objects.get(user=user)
    assert p.status == Moderation.PENDING and p.agreed_at
    assert p.faith_answers['relations'] == 'no'
    assert p.label('marital') == 'Не был женат'


def test_wizard_requires_pledges_and_faith(client):
    user = User.objects.create_user('w2', 'w2@x.com', 'x')
    client.force_login(user)
    data = wizard_data(relocation='stay')
    data.pop('agree_rules')
    data.pop('faith_fast')
    resp = client.post('/nikah/create/', data)
    assert resp.status_code == 200 and not NikahProfile.objects.filter(user=user).exists()
    assert resp.context['step'] == 14   # вернули к первому шагу с ошибкой


def test_wizard_rejects_contacts_in_text(client):
    user = User.objects.create_user('w3', 'w3@x.com', 'x')
    client.force_login(user)
    resp = client.post('/nikah/create/', wizard_data(relocation='stay', about='Пишите в телеграм @ahmad_uz, жду'))
    assert resp.status_code == 200 and resp.context['step'] == 11
    assert not NikahProfile.objects.filter(user=user).exists()


def test_wizard_sister_labels_and_rules(client):
    user = User.objects.create_user('s', 's@x.com', 'x')
    client.force_login(user)
    client.post('/nikah/create/', wizard_data('F', relocation='any', marital='divorced', polygyny='discuss'))
    p = NikahProfile.objects.get(user=user)
    assert p.label('marital') == 'Разведена' and p.wife_number is None and p.polygyny == 'discuss'
    # «замужем» для сестры не допускается
    user2 = User.objects.create_user('s2', 's2@x.com', 'x')
    client.force_login(user2)
    client.post('/nikah/create/', wizard_data('F', relocation='any', marital='married'))
    assert not NikahProfile.objects.filter(user=user2).exists()


def test_wizard_photo_stored_encrypted(client):
    user = User.objects.create_user('ph', 'ph@x.com', 'x')
    client.force_login(user)
    client.post('/nikah/create/', wizard_data(relocation='stay', photo_mode='exchange', photo=png()))
    p = NikahProfile.objects.get(user=user)
    assert p.has_photo and p.photo_private.name.endswith('.bin')
    with p.photo_private.open('rb') as f:
        assert not f.read(4).startswith(b'\xff\xd8')   # на диске не JPEG, а шифротекст


def test_wizard_exchange_requires_photo(client):
    user = User.objects.create_user('np', 'np@x.com', 'x')
    client.force_login(user)
    resp = client.post('/nikah/create/', wizard_data(relocation='stay', photo_mode='exchange'))
    assert resp.context['step'] == 13


# ---------- лента ----------

def test_feed_shows_only_opposite_gender_approved(client):
    me = make_profile('b@x.com', 'M')
    make_profile('s1@x.com', 'F', name='Видна')
    make_profile('s2@x.com', 'F', name='НаПроверке', status=Moderation.PENDING)
    make_profile('b2@x.com', 'M', name='Брат')
    client.force_login(me.user)
    html = client.get('/nikah/').content.decode()
    assert 'Видна' in html and 'НаПроверке' not in html and 'Брат,' not in html


def test_guest_sees_intro_not_profiles(client):
    make_profile('s1@x.com', 'F', name='Видна')
    html = client.get('/nikah/').content.decode()
    assert 'Как устроен сервис' in html and 'Видна' not in html


def test_compatibility_higher_for_similar():
    a = make_profile('a@x.com', 'M')
    close = make_profile('c@x.com', 'F')
    far = make_profile('f@x.com', 'F', aqida='sufi', where_allah='everywhere', prayer='none', age=60,
                       children_want='no', country='Канада', relocation='stay')
    assert services.compatibility(a, close)[0] > services.compatibility(a, far)[0]


# ---------- интерес → пара → фото → чат ----------

def test_mutual_interest_without_photos_opens_chat(client):
    b = make_profile('b@x.com', 'M')
    s = make_profile('s@x.com', 'F')
    client.force_login(b.user)
    client.post(f'/nikah/{s.pk}/interest/')
    assert not NikahMatch.objects.exists()
    client.force_login(s.user)
    resp = client.post(f'/nikah/{b.pk}/interest/')
    m = NikahMatch.objects.get()
    assert resp.url == f'/nikah/match/{m.pk}/'
    assert m.stage == NikahMatch.CHAT and m.thread
    assert set(m.thread.participants.values_list('pk', flat=True)) == {b.user.pk, s.user.pk}


def _match_with_photos():
    b = make_profile('b@x.com', 'M', photo_mode='exchange')
    s = make_profile('s@x.com', 'F', photo_mode='exchange')
    for p, c in ((b, 'blue'), (s, 'red')):
        services.store_photo(p, png(c))
        p.save()
    services.send_interest(b, s)
    return b, s, services.send_interest(s, b)


def test_photo_exchange_sister_first_then_chat(client):
    b, s, m = _match_with_photos()
    assert m.stage == NikahMatch.PHOTOS
    # брат не может смотреть первым
    client.force_login(b.user)
    assert client.get(f'/nikah/match/{m.pk}/photo/').status_code == 403
    # сестра: обещание → фото с водяным знаком → «продолжить»
    client.force_login(s.user)
    assert client.post(f'/nikah/match/{m.pk}/open/', {}).status_code == 302
    assert client.get(f'/nikah/match/{m.pk}/photo/').status_code == 403   # без обещания не открыто
    client.post(f'/nikah/match/{m.pk}/open/', {'oath': '1'})
    photo = client.get(f'/nikah/match/{m.pk}/photo/')
    assert photo.status_code == 200 and photo['Content-Type'] == 'image/jpeg'
    assert 'no-store' in photo['Cache-Control']
    client.post(f'/nikah/match/{m.pk}/decide/', {'ok': '1'})
    # очередь брата
    client.force_login(b.user)
    client.post(f'/nikah/match/{m.pk}/open/', {'oath': '1'})
    assert client.get(f'/nikah/match/{m.pk}/photo/').status_code == 200
    client.post(f'/nikah/match/{m.pk}/decide/', {'ok': '1'})
    m.refresh_from_db()
    assert m.stage == NikahMatch.CHAT and m.thread_id
    # после решения фото больше не открыть
    assert client.get(f'/nikah/match/{m.pk}/photo/').status_code == 403


def test_photo_timeout_counts_as_refusal(client):
    _b, s, m = _match_with_photos()
    services.open_photo(m, 'sister')
    NikahMatch.objects.filter(pk=m.pk).update(sister_viewed_at=timezone.now() - timedelta(minutes=11))
    client.force_login(s.user)
    client.get(f'/nikah/match/{m.pk}/')
    m.refresh_from_db()
    assert m.stage == NikahMatch.CLOSED and m.sister_ok is False


def test_outsider_cannot_see_match(client):
    _b, _s, m = _match_with_photos()
    other = make_profile('o@x.com', 'F')
    client.force_login(other.user)
    assert client.get(f'/nikah/match/{m.pk}/').status_code == 404
    assert client.get(f'/nikah/match/{m.pk}/photo/').status_code == 404


def test_pending_profile_cannot_send_interest(client):
    b = make_profile('b@x.com', 'M', status=Moderation.PENDING)
    s = make_profile('s@x.com', 'F')
    client.force_login(b.user)
    client.post(f'/nikah/{s.pk}/interest/')
    assert not NikahInterest.objects.exists()


def test_brother_pays_for_chat_when_price_set(client):
    st = SiteSettings.get_solo()
    st.nikah_chat_price = 10_000
    st.save()
    b = make_profile('b@x.com', 'M')
    s = make_profile('s@x.com', 'F')
    services.send_interest(b, s)
    m = services.send_interest(s, b)
    assert m.stage == NikahMatch.CHAT and m.thread is None      # ждём оплату брата
    wallet.credit(b.user, 50_000, Transaction.TOPUP)
    client.force_login(b.user)
    client.post(f'/nikah/match/{m.pk}/pay/')
    m.refresh_from_db()
    assert m.thread_id and wallet.balance_of(b.user) == 40_000


def test_boost_profile(client):
    b = make_profile('b@x.com', 'M')
    wallet.credit(b.user, 50_000, Transaction.TOPUP)
    client.force_login(b.user)
    client.post('/nikah/me/boost/')
    b.refresh_from_db()
    assert b.is_boosted


def test_pages_render(client):
    b, s, m = _match_with_photos()
    client.force_login(b.user)
    for url in ('/nikah/', '/nikah/premium/', '/nikah/interests/', '/nikah/interests/?show=mutual', '/nikah/interests/?show=sent',
                '/nikah/saved/', '/nikah/chats/', '/nikah/me/', '/nikah/edit/', '/nikah/how/',
                f'/nikah/{s.pk}/', f'/nikah/match/{m.pk}/'):
        assert client.get(url).status_code == 200, url


# ---------- Telegram ----------

def _init_data(token, tg_id=777, auth_date=None):
    fields = {'auth_date': str(auth_date or int(time.time())), 'query_id': 'Q1',
              'user': json.dumps({'id': tg_id, 'first_name': 'Иса', 'username': 'isa'})}
    check = '\n'.join(f'{k}={v}' for k, v in sorted(fields.items()))
    secret = hmac.new(b'WebAppData', token.encode(), hashlib.sha256).digest()
    fields['hash'] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def test_telegram_webapp_login(client, settings):
    settings.TELEGRAM_BOT_TOKEN = '123:ABC'
    resp = client.post('/accounts/telegram/webapp/', {'init_data': _init_data('123:ABC')})
    assert resp.json()['ok']
    user = User.objects.get(telegram_id=777)
    assert int(client.session['_auth_user_id']) == user.pk


def test_telegram_rejects_forged_or_old(client, settings):
    settings.TELEGRAM_BOT_TOKEN = '123:ABC'
    assert client.post('/accounts/telegram/webapp/', {'init_data': _init_data('999:WRONG')}).status_code == 403
    old = _init_data('123:ABC', auth_date=int(time.time()) - 3 * 86400)
    assert client.post('/accounts/telegram/webapp/', {'init_data': old}).status_code == 403
    assert not User.objects.filter(telegram_id=777).exists()


# ---------- колода: свайпы, лимит, фильтры, премиум ----------

def _json_post(client, url, **data):
    return client.post(url, {'from_deck': '1', **data}, HTTP_ACCEPT='application/json')


def test_skip_hides_profile_and_restore_brings_back(client):
    b = make_profile('b@x.com', 'M')
    s = make_profile('s@x.com', 'F', name='Сафия')
    client.force_login(b.user)
    assert 'Сафия' in client.get('/nikah/').content.decode()
    assert _json_post(client, f'/nikah/{s.pk}/skip/').json()['ok']
    assert 'Сафия' not in client.get('/nikah/').content.decode()
    wallet.credit(b.user, 50_000, Transaction.TOPUP)
    client.post('/nikah/restore/')
    assert wallet.balance_of(b.user) == 40_000            # 10 000 за возврат
    assert 'Сафия' in client.get('/nikah/').content.decode()


def test_daily_limit_and_premium(client):
    st = SiteSettings.get_solo()
    st.nikah_daily_limit = 2
    st.save()
    b = make_profile('b@x.com', 'M')
    sisters = [make_profile(f's{i}@x.com', 'F') for i in range(4)]
    client.force_login(b.user)
    assert _json_post(client, f'/nikah/{sisters[0].pk}/skip/').json()['left'] == 1
    assert _json_post(client, f'/nikah/{sisters[1].pk}/interest/').json()['left'] == 0
    assert _json_post(client, f'/nikah/{sisters[2].pk}/skip/').status_code == 429
    assert 'на сегодня закончились' in client.get('/nikah/').content.decode()
    wallet.credit(b.user, 100_000, Transaction.TOPUP)
    client.post('/nikah/premium/')
    b.refresh_from_db()
    assert b.is_premium and wallet.balance_of(b.user) == 51_000
    assert _json_post(client, f'/nikah/{sisters[2].pk}/skip/').json()['left'] is None   # без лимита


def test_swipe_right_mutual_returns_match_url(client):
    b = make_profile('b@x.com', 'M')
    s = make_profile('s@x.com', 'F')
    services.send_interest(s, b)
    client.force_login(b.user)
    j = _json_post(client, f'/nikah/{s.pk}/interest/').json()
    assert j['match'].startswith('/nikah/match/')


def test_filters_saved_in_session(client):
    b = make_profile('b@x.com', 'M')
    make_profile('s1@x.com', 'F', name='Тюрчанка', nationality='татарка', height=165)
    make_profile('s2@x.com', 'F', name='Арабка', nationality='египтянка', height=158)
    client.force_login(b.user)
    client.post('/nikah/filters/', {'nation_group': 'turkic', 'height_min': '160', 'height_max': '230'})
    html = client.get('/nikah/').content.decode()
    assert 'Тюрчанка' in html and 'Арабка' not in html
    client.post('/nikah/filters/', {'reset': '1'})
    assert 'Арабка' in client.get('/nikah/').content.decode()


def test_premium_only_online_filter(client):
    b = make_profile('b@x.com', 'M')
    make_profile('s1@x.com', 'F', name='Давно')
    client.force_login(b.user)
    client.post('/nikah/filters/', {'online': '1'})
    assert 'Давно' in client.get('/nikah/').content.decode()   # без премиума фильтр не действует


def test_cleanup_command_closes_expired(client):
    from django.core.management import call_command
    _b, _s, m = _match_with_photos()
    services.open_photo(m, 'sister')
    NikahMatch.objects.filter(pk=m.pk).update(sister_viewed_at=timezone.now() - timedelta(minutes=30))
    call_command('nikah_cleanup')
    m.refresh_from_db()
    assert m.stage == NikahMatch.CLOSED


# ---------- отделение модуля ----------

def test_export_import_roundtrip(tmp_path):
    from apps.nikah.transfer import export_zip, import_zip
    _b, _s, m = _match_with_photos()
    NikahMatch.objects.filter(pk=m.pk).update(stage=NikahMatch.CHAT)
    m.refresh_from_db()
    services._ensure_chat(m)
    path = tmp_path / 'nikah.zip'
    counts = export_zip(path)
    assert counts['profiles'] == 2 and counts['matches'] == 1
    raw = path.read_bytes()
    assert 'Имя'.encode() not in raw and b'b@x.com' not in raw        # в архиве всё зашифровано
    # «новый сервер»: чистим всё и загружаем
    NikahMatch.objects.all().delete()
    NikahProfile.objects.all().delete()
    User.objects.all().delete()
    report = import_zip(path)
    assert report['users_new'] == 2 and report['profiles'] == 2 and report['matches'] == 1
    m2 = NikahMatch.objects.get()
    assert m2.thread.messages.exists()
    assert NikahProfile.objects.get(user__email='s@x.com').has_photo
    assert User.objects.get(email='b@x.com').check_password('x')


def test_site_mode_nikah(client, settings):
    settings.SITE_MODE = 'nikah'
    assert client.get('/').url == '/nikah/'
    assert client.get('/buy/').status_code == 404
    assert client.get('/nikah/').status_code == 200
