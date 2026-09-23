"""Логика никяха: совместимость, запрет контактов, фото (шифрование, водяной знак),
интерес → пара → обмен фото → чат."""
import io
import re
import uuid
from datetime import timedelta

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.chat.crypto import decrypt_bytes, encrypt_bytes
from apps.core.models import SiteSettings

from .models import NikahInterest, NikahMatch, NikahProfile

# --- контакты в текстах анкеты запрещены ---
CONTACT_PATTERNS = [
    re.compile(r'(?:\+?\d[\s\-()]*){7,}'),                             # телефон
    re.compile(r'(?<![\w.])@[a-z0-9_]{4,}', re.IGNORECASE),                      # @ник
    re.compile(r'https?://|www\.|t\.me/|\b[\w.-]+\.(?:com|ru|uz|kz|org|net|me|io)\b', re.IGNORECASE),
    re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+'),                             # email
    re.compile(r'\b(?:телеграм|телеграмм|telegram|tg|ватсап|вацап|whats?app|инстаграм|инста|instagram|'
               r'imo|вайбер|viber|signal|ig)\b', re.IGNORECASE),
]


def has_contacts(text: str) -> bool:
    return any(p.search(text or '') for p in CONTACT_PATTERNS)


# --- совместимость ---
def compatibility(me: NikahProfile, other: NikahProfile) -> tuple[int, list[str]]:
    """Процент совпадения (0–100) и что совпало — для карточки анкеты."""
    score, why = 0, []

    def same(field):
        a, b = getattr(me, field), getattr(other, field)
        return bool(a) and a == b

    athari, kalam = {'athari', 'salafi'}, {'ashari', 'maturidi'}
    if same('aqida'):
        score += 25
        why.append('Одно вероубеждение')
    elif {me.aqida, other.aqida} <= athari or {me.aqida, other.aqida} <= kalam:
        score += 20
        why.append('Близкие вероубеждения')
    elif 'sunna' in (me.aqida, other.aqida) or 'other' in (me.aqida, other.aqida):
        score += 10

    if same('where_allah'):
        score += 15
        why.append('Одинаковый ответ «где Аллах»')
    elif 'unsure' in (me.where_allah, other.where_allah):
        score += 6

    if same('madhhab'):
        score += 10
        why.append('Один мазхаб')
    elif 'none' in (me.madhhab, other.madhhab):
        score += 6
    elif me.madhhab and other.madhhab:
        score += 3

    if same('prayer'):
        score += 15
        why.append('Одинаково с намазом')
    elif 'none' not in (me.prayer, other.prayer):
        score += 8

    fits_me = me.age_from <= other.age <= me.age_to
    fits_other = other.age_from <= me.age <= other.age_to
    score += 8 * fits_me + 7 * fits_other
    if fits_me and fits_other:
        why.append('Возраст подходит обоим')

    if same('children_want'):
        score += 10
        why.append('Одинаково о детях')
    elif 'unsure' in (me.children_want, other.children_want):
        score += 5

    if me.country and me.country.lower() == (other.country or '').lower():
        score += 10
        why.append('Одна страна')
    elif {'abroad', 'any'} & {me.relocation, other.relocation}:
        score += 7
    else:
        score += 2
    return min(score, 100), why


# --- фото: хранится зашифрованным, показывается с водяным знаком ---
def store_photo(profile: NikahProfile, upload) -> None:
    from PIL import Image, ImageOps

    img = ImageOps.exif_transpose(Image.open(upload)).convert('RGB')   # без EXIF и геометок
    img.thumbnail((1600, 1600))
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=86, optimize=True)
    if profile.photo_private:
        profile.photo_private.delete(save=False)
    profile.photo_private.save(f'{uuid.uuid4().hex}.bin', ContentFile(encrypt_bytes(buf.getvalue())), save=False)


def watermarked_photo(profile: NikahProfile, viewer) -> bytes:
    """Фото с диагональной сеткой «ilm4 · ID смотрящего · дата» — утечку видно сразу."""
    from PIL import Image, ImageDraw, ImageFont

    with profile.photo_private.open('rb') as f:
        img = Image.open(io.BytesIO(decrypt_bytes(f.read()))).convert('RGBA')
    text = f'ilm4 · ID {viewer.pk} · {timezone.localtime():%d.%m.%Y %H:%M}'
    size = max(16, img.width // 26)
    try:
        font = ImageFont.truetype('DejaVuSans.ttf', size)
    except OSError:
        font = ImageFont.load_default(size=size)
    layer = Image.new('RGBA', (img.width * 2, img.height * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    step_y, step_x = size * 4, int(size * len(text) * 0.62)
    for y in range(0, layer.height, step_y):
        for x in range(-(y // step_y % 2) * step_x // 2, layer.width, step_x):
            draw.text((x, y), text, font=font, fill=(255, 255, 255, 70))
    layer = layer.rotate(30, resample=Image.BICUBIC)
    left, top = (layer.width - img.width) // 2, (layer.height - img.height) // 2
    img.alpha_composite(layer.crop((left, top, left + img.width, top + img.height)))
    out = io.BytesIO()
    img.convert('RGB').save(out, 'JPEG', quality=82)
    return out.getvalue()


def photo_minutes() -> int:
    return SiteSettings.get_solo().nikah_photo_minutes or 10


# --- уведомления: колокольчик на сайте + Telegram, если человек заходил оттуда ---
def notify(profile: NikahProfile, text: str, url: str) -> None:
    from apps.accounts.telegram import send_message
    from apps.core.models import Notification

    Notification.objects.create(user=profile.user, text=text, url=url)
    send_message(profile.user, text, url)


# --- интерес → пара ---
@transaction.atomic
def send_interest(me: NikahProfile, other: NikahProfile) -> NikahMatch | None:
    """Поставить «❤». Встречный интерес уже есть — создаётся пара."""
    if me.gender == other.gender or me.pk == other.pk:
        raise ValueError('Интерес можно проявить только к анкете противоположного пола')
    _, created = NikahInterest.objects.get_or_create(from_profile=me, to_profile=other)
    if not NikahInterest.objects.filter(from_profile=other, to_profile=me).exists():
        if created:
            notify(other, 'Кто-то проявил интерес к вашей анкете никяха', '/nikah/interests/')
        return None
    sister, brother = (me, other) if me.gender == 'F' else (other, me)
    match, made = NikahMatch.objects.get_or_create(sister=sister, brother=brother)
    if made:
        if not (sister.shares_photo and brother.shares_photo):
            match.stage = NikahMatch.CHAT       # кто-то выбрал «без фото» — сразу к переписке
            match.save(update_fields=['stage'])
            _ensure_chat(match)
        for p in (sister, brother):
            notify(p, 'Взаимная симпатия! Откройте, что дальше', f'/nikah/match/{match.pk}/')
    return match


def withdraw_interest(me: NikahProfile, other: NikahProfile) -> None:
    NikahInterest.objects.filter(from_profile=me, to_profile=other).delete()


def refresh(match: NikahMatch) -> NikahMatch:
    """Молчание дольше отведённых минут после открытия фото = отказ."""
    if match.stage != NikahMatch.PHOTOS:
        return match
    limit = timedelta(minutes=photo_minutes())
    now = timezone.now()
    for side in ('sister', 'brother'):
        opened = getattr(match, f'{side}_viewed_at')
        if opened and getattr(match, f'{side}_ok') is None and now - opened > limit:
            setattr(match, f'{side}_ok', False)
            _close(match)
            cleanup_tg_photos(match)
            break
    return match


def turn(match: NikahMatch) -> str | None:
    """Чья очередь смотреть фото: сестра первой, затем брат."""
    if match.stage != NikahMatch.PHOTOS:
        return None
    if match.sister_ok is None:
        return 'sister'
    if match.sister_ok and match.brother_ok is None:
        return 'brother'
    return None


def seconds_left(match: NikahMatch, side: str) -> int:
    opened = getattr(match, f'{side}_viewed_at')
    if not opened:
        return photo_minutes() * 60
    return max(0, int((opened + timedelta(minutes=photo_minutes()) - timezone.now()).total_seconds()))


@transaction.atomic
def open_photo(match: NikahMatch, side: str) -> None:
    match = NikahMatch.objects.select_for_update().get(pk=match.pk)
    if turn(match) != side:
        raise ValueError('Сейчас не ваша очередь')
    if not getattr(match, f'{side}_viewed_at'):
        setattr(match, f'{side}_viewed_at', timezone.now())
        match.save(update_fields=[f'{side}_viewed_at'])


@transaction.atomic
def decide(match: NikahMatch, side: str, ok: bool) -> NikahMatch:
    match = refresh(NikahMatch.objects.select_for_update().get(pk=match.pk))
    if turn(match) != side or not getattr(match, f'{side}_viewed_at'):
        raise ValueError('Решение уже принято или время вышло')
    setattr(match, f'{side}_ok', ok)
    match.save(update_fields=[f'{side}_ok'])
    cleanup_tg_photos(match)
    if not ok:
        _close(match)
    elif side == 'sister':
        notify(match.brother, 'Сестра посмотрела ваше фото и готова продолжить — ваша очередь',
               f'/nikah/match/{match.pk}/')
    else:
        match.stage = NikahMatch.CHAT
        match.save(update_fields=['stage'])
        _ensure_chat(match)
        for p in (match.sister, match.brother):
            notify(p, 'Оба согласны — чат открыт. БаракаЛлаху фикум!', f'/nikah/match/{match.pk}/')
    return match


# --- фото через Telegram (защищённое сообщение) ---
def tg_ready(user) -> bool:
    from apps.accounts.telegram import bot_token
    return bool(bot_token() and getattr(user, 'telegram_id', None))


def send_photo_to_telegram(match: NikahMatch, side: str, user) -> bool:
    """Отправить фото собеседника в Telegram: защищено от пересылки и сохранения,
    бот удалит сообщение, когда выйдет время или будет принято решение."""
    from apps.accounts.telegram import send_protected_photo

    partner = match.brother if side == 'sister' else match.sister
    msg_id = send_protected_photo(
        user, watermarked_photo(partner, user),
        f'Фото исчезнет через {photo_minutes()} мин. Скриншот и пересылка запрещены — нарушение = блокировка.',
        f'/nikah/match/{match.pk}/')
    if msg_id:
        setattr(match, f'{side}_tg_msg', msg_id)
        match.save(update_fields=[f'{side}_tg_msg'])
    return bool(msg_id)


def cleanup_tg_photos(match: NikahMatch, force: bool = False) -> None:
    """Удалить фото из Telegram: после решения, по таймеру или при закрытии пары."""
    from apps.accounts.telegram import delete_message

    for side in ('sister', 'brother'):
        msg = getattr(match, f'{side}_tg_msg')
        if not msg:
            continue
        decided = getattr(match, f'{side}_ok') is not None or match.stage != NikahMatch.PHOTOS
        if force or decided or seconds_left(match, side) <= 0:
            viewer = (match.sister if side == 'sister' else match.brother).user
            delete_message(viewer, msg)
            setattr(match, f'{side}_tg_msg', None)
            match.save(update_fields=[f'{side}_tg_msg'])


def _close(match: NikahMatch) -> None:
    match.stage = NikahMatch.CLOSED
    match.closed_at = timezone.now()
    match.save()


def chat_price() -> int:
    return SiteSettings.get_solo().nikah_chat_price


def _ensure_chat(match: NikahMatch):
    """Диалог создаётся, когда чат открыт и (если есть цена) брат оплатил."""
    if match.thread_id or (chat_price() and not match.chat_paid):
        return match.thread
    from apps.chat.models import Message, Thread

    thread = Thread.objects.create(subject='Никях · знакомство')
    thread.participants.add(match.sister.user, match.brother.user)
    Message.objects.create(thread=thread, sender=match.sister.user, kind=Message.SYSTEM,
                           body='Чат никяха открыт. Помните об адабе: цель — никях, контакты и фото — '
                                'по взаимному согласию. Бойтесь Аллаха.')
    match.thread = thread
    match.save(update_fields=['thread'])
    return thread


@transaction.atomic
def pay_chat(match: NikahMatch, user) -> None:
    """Брат оплачивает открытие чата (если в настройках цена > 0)."""
    from apps.wallet import services as wallet
    from apps.wallet.models import Transaction

    match = NikahMatch.objects.select_for_update().get(pk=match.pk)
    price = chat_price()
    if match.stage != NikahMatch.CHAT or match.brother.user_id != user.pk:
        raise ValueError('Оплата сейчас недоступна')
    if price and not match.chat_paid:
        wallet.debit(user, price, Transaction.PURCHASE, ref=f'nikah:chat:{match.pk}', note='Никях: открытие чата')
    match.chat_paid = True
    match.save(update_fields=['chat_paid'])
    _ensure_chat(match)
