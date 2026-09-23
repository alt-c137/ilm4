"""Никях в Telegram-боте: модерация анкет кнопками в чате модераторов и верификация
видео-кружком. Видео не сохраняется на нашем сервере — бот лишь копирует его модераторам.
"""
from django.core.cache import cache
from django.utils import timezone

from apps.accounts.telegram import api, open_button
from apps.core.models import Moderation
from apps.tgbot.dispatch import is_moderator, moderation_chat, reply

from . import choices as C
from .models import NikahProfile

VERIFY_TTL = 24 * 3600


def _summary(p: NikahProfile) -> str:
    flags = [q for key, q, _o in C.FAITH_QUESTIONS if p.faith_answers.get(key) == C.FAITH_RED_FLAGS.get(key)]
    lines = [
        f'📝 Анкета #{p.pk} — {p.get_gender_display()}, {p.display_name}, {p.age}',
        f'📍 {p.place or "—"}{" · " + p.nationality if p.nationality else ""}',
        f'☪ {p.label("aqida") or "—"} · {p.label("madhhab") or "—"} · намаз: {p.label("prayer") or "—"}',
        f'👪 {p.label("marital") or "—"} · фото: {p.label("photo_mode")}',
        '', f'Манхадж: {p.manhaj_text[:600]}', '', f'О себе: {p.about[:600]}', '',
        f'Кого ищет: {p.partner_expectations[:500]}',
    ]
    if flags:
        lines += ['', '⚠️ Тревожные закрытые ответы: ' + '; '.join(flags)]
    return '\n'.join(lines)[:4000]


def send_for_moderation(p: NikahProfile) -> bool:
    """Новая/изменённая анкета → в чат модераторов (фото — защищённым сообщением)."""
    chat = moderation_chat()
    if not chat:
        return False
    if p.has_photo:
        from .services import watermarked_photo

        class _Mod:   # водяной знак «MOD» вместо ID пользователя
            pk = 'MOD'
        api('sendPhoto', {'chat_id': chat, 'protect_content': 'true', 'has_spoiler': 'true',
                          'caption': f'Фото анкеты #{p.pk}'},
            files={'photo': ('p.jpg', watermarked_photo(p, _Mod), 'image/jpeg')}, timeout=20)
    kb = {'inline_keyboard': [[{'text': '✅ Одобрить', 'callback_data': f'nk:mod:ok:{p.pk}'},
                               {'text': '❌ Отклонить', 'callback_data': f'nk:mod:no:{p.pk}'}]]}
    return bool(api('sendMessage', {'chat_id': chat, 'text': _summary(p), 'reply_markup': kb, 'protect_content': 'true'}))


def approve(p: NikahProfile) -> None:
    """Одобрение (из Telegram или админки): публикация + бонус пригласившему."""
    from datetime import timedelta

    from apps.core.models import SiteSettings

    from .services import notify

    p.status = Moderation.APPROVED
    p.save(update_fields=['status'])
    notify(p, 'Ваша анкета одобрена и видна в ленте. Бисмиллях!', '/nikah/')
    ref = p.referred_by
    if ref and not p.ref_bonus_given:
        days = SiteSettings.get_solo().nikah_ref_bonus_days
        if days:
            base = ref.premium_until if ref.is_premium else timezone.now()
            ref.premium_until = base + timedelta(days=days)
            ref.save(update_fields=['premium_until'])
            notify(ref, f'Приглашённый вами человек прошёл модерацию — +{days} дн. премиума!', '/nikah/premium/')
        NikahProfile.objects.filter(pk=p.pk).update(ref_bonus_given=True)


def reject(p: NikahProfile) -> None:
    from .services import notify

    p.status = Moderation.REJECTED
    p.save(update_fields=['status'])
    notify(p, 'Анкета не прошла проверку. Уберите контакты и лишнее, дополните описание — и отправьте снова.',
           '/nikah/edit/')


# ---------- верификация кружком ----------

def verify_text(p: NikahProfile) -> str:
    return (f'✅ Верификация\n\nПроверяем, что анкету ведёт живой человек.\n'
            f'🔒 Запись увидит только модератор; на нашем сервере она не хранится.\n\n'
            f'📹 Запишите видео-кружок и скажите вслух: «{p.display_name}, {p.age}».\n\n'
            f'Лицо должно быть видно целиком, при нормальном свете. Кружок с потолком, стеной или в темноте '
            f'модератор отклонит. Фото не подходит — нужен именно кружок.\n\n'
            f'Как записать: в поле ввода нажмите на 🎤 — он сменится на 📹, затем удерживайте и говорите.')


def send_verify_instructions(tg_id: int) -> bool:
    p = NikahProfile.objects.filter(user__telegram_id=tg_id).first()
    if not p:
        return False
    cache.set(f'nkverify:{tg_id}', p.pk, VERIFY_TTL)
    return bool(reply(tg_id, verify_text(p)))


def video_note(msg: dict) -> None:
    tg_id = msg['from']['id']
    p = NikahProfile.objects.filter(user__telegram_id=tg_id).first()
    if not p:
        reply(tg_id, 'Сначала откройте никях и заполните анкету — потом пройдёте верификацию.',
              open_button('Открыть никях'))
        return
    if p.verified:
        reply(tg_id, 'Вы уже верифицированы ✅')
        return
    if not msg.get('video_note'):
        reply(tg_id, 'Нужен именно видео-кружок (не обычное видео). Нажмите 🎤, чтобы он сменился на 📹, и удерживайте.')
        return
    chat = moderation_chat()
    if not chat:
        reply(tg_id, 'Верификация временно недоступна — попробуйте позже.')
        return
    api('copyMessage', {'chat_id': chat, 'from_chat_id': tg_id, 'message_id': msg['message_id'],
                        'protect_content': 'true'})
    kb = {'inline_keyboard': [[{'text': '✅ Лицо видно, фраза верна', 'callback_data': f'nk:ver:ok:{p.pk}'}],
                              [{'text': '❌ Отклонить', 'callback_data': f'nk:ver:no:{p.pk}'}]]}
    api('sendMessage', {'chat_id': chat, 'reply_markup': kb,
                        'text': f'🎥 Верификация анкеты #{p.pk}: должен(на) сказать «{p.display_name}, {p.age}»'})
    cache.delete(f'nkverify:{tg_id}')
    reply(tg_id, 'Спасибо! Кружок отправлен модератору — обычно проверяем в течение суток.')


# ---------- кнопки модераторов ----------

def callback(cq: dict) -> str:
    """nk:mod:ok:<id> / nk:mod:no / nk:ver:ok / nk:ver:no. Возвращает текст всплывашки."""
    from apps.accounts.models import AuditLog

    from .services import notify

    if not is_moderator(cq):
        return 'Нет прав модератора'
    try:
        _nk, kind, verdict, pk = cq['data'].split(':')
        p = NikahProfile.objects.get(pk=int(pk))
    except (ValueError, NikahProfile.DoesNotExist):
        return 'Анкета не найдена'
    who = cq['from'].get('username') or cq['from'].get('first_name') or cq['from']['id']
    if kind == 'mod':
        (approve if verdict == 'ok' else reject)(p)
        result = '✅ Одобрено' if verdict == 'ok' else '❌ Отклонено'
    else:
        if verdict == 'ok':
            p.verified, p.verified_at = True, timezone.now()
            p.save(update_fields=['verified', 'verified_at'])
            notify(p, 'Верификация пройдена — на анкете значок ✅', '/nikah/me/')
        else:
            notify(p, 'Верификация не пройдена: на кружке должно быть видно лицо и слышна фраза. Попробуйте ещё раз.',
                   '/nikah/settings/')
        result = '✅ Верифицирован' if verdict == 'ok' else '❌ Верификация отклонена'
    AuditLog.objects.create(action=f'Никях (Telegram): {result}', target=f'анкета #{p.pk}, модератор @{who}')
    m = cq.get('message', {})
    api('editMessageText', {'chat_id': m.get('chat', {}).get('id'), 'message_id': m.get('message_id'),
                            'text': (m.get('text') or '')[:3800] + f'\n\n{result} — @{who}'})
    return result
