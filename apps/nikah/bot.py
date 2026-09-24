"""Никях в Telegram-боте: модерация анкет кнопками в чате модераторов и верификация
видео-кружком. Видео не сохраняется на нашем сервере — бот лишь копирует его модераторам.
"""
from django.core.cache import cache
from django.utils import timezone
from django.utils.text import format_lazy
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from apps.accounts.telegram import api, open_button
from apps.core.models import Moderation
from apps.tgbot.dispatch import is_moderator, moderation_chat, reply

from . import choices as C
from .models import NikahProfile

VERIFY_TTL = 24 * 3600


def _summary(p: NikahProfile) -> str:
    flags = [q for key, q, _o in C.FAITH_QUESTIONS if p.faith_answers.get(key) == C.FAITH_RED_FLAGS.get(key)]
    lines = [
        _('📝 Анкета #{v1} — {v3}, {v5}, {v7}').format(v1=p.pk, v3=p.get_gender_display(), v5=p.display_name, v7=p.age),
        f'📍 {p.place or "—"}{" · " + p.nationality if p.nationality else ""}',
        _('☪ {v1} · {v3} · намаз: {v5}').format(v1=p.label('aqida') or '—', v3=p.label('madhhab') or '—', v5=p.label('prayer') or '—'),
        _('👪 {v1} · фото: {v3}').format(v1=p.label('marital') or '—', v3=p.label('photo_mode')),
        '', _('Манхадж: {v1}').format(v1=p.manhaj_text[:600]), '', _('О себе: {v1}').format(v1=p.about[:600]), '',
        _('Кого ищет: {v1}').format(v1=p.partner_expectations[:500]),
    ]
    if flags:
        lines += ['', _('⚠️ Тревожные закрытые ответы: ') + '; '.join(flags)]
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
                          'caption': _('Фото анкеты #{v1}').format(v1=p.pk)},
            files={'photo': ('p.jpg', watermarked_photo(p, _Mod), 'image/jpeg')}, timeout=20)
    kb = {'inline_keyboard': [[{'text': _('✅ Одобрить'), 'callback_data': f'nk:mod:ok:{p.pk}'},
                               {'text': _('❌ Отклонить'), 'callback_data': f'nk:mod:no:{p.pk}'}]]}
    return bool(api('sendMessage', {'chat_id': chat, 'text': _summary(p), 'reply_markup': kb, 'protect_content': 'true'}))


def approve(p: NikahProfile) -> None:
    """Одобрение (из Telegram или админки): публикация + бонус пригласившему."""
    from datetime import timedelta

    from apps.core.models import SiteSettings

    from .services import notify

    p.status = Moderation.APPROVED
    p.save(update_fields=['status'])
    notify(p, _lazy('Ваша анкета одобрена и видна в ленте. Бисмиллях!'), '/nikah/')
    ref = p.referred_by
    if ref and not p.ref_bonus_given:
        days = SiteSettings.get_solo().nikah_ref_bonus_days
        if days:
            base = ref.premium_until if ref.is_premium else timezone.now()
            ref.premium_until = base + timedelta(days=days)
            ref.save(update_fields=['premium_until'])
            notify(ref, format_lazy(_lazy('Приглашённый вами человек прошёл модерацию — +{days} дн. премиума!'), days=days), '/nikah/premium/')
        NikahProfile.objects.filter(pk=p.pk).update(ref_bonus_given=True)


def reject(p: NikahProfile, reason: str = '') -> None:
    from .services import notify

    p.status = Moderation.REJECTED
    p.save(update_fields=['status'])
    text = _lazy('Анкета не прошла проверку. Уберите контакты и лишнее, дополните описание — и отправьте снова.')
    if reason:
        text = format_lazy('{t}\n{label}: {r}', t=text, label=_lazy('Причина'), r=reason)
    notify(p, text, '/nikah/edit/')


# ---------- верификация кружком ----------

def verify_text(p: NikahProfile) -> str:
    return (_('✅ Верификация\n\nПроверяем, что анкету ведёт живой человек.\n🔒 Запись увидит только модератор; на нашем сервере она не хранится.\n\n📹 Запишите видео-кружок и скажите вслух: «{v1}, {v3}».\n\nЛицо должно быть видно целиком, при нормальном свете. Кружок с потолком, стеной или в темноте модератор отклонит. Фото не подходит — нужен именно кружок.\n\nКак записать: в поле ввода нажмите на 🎤 — он сменится на 📹, затем удерживайте и говорите.').format(v1=p.display_name, v3=p.age))


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
        reply(tg_id, _('Сначала откройте никях и заполните анкету — потом пройдёте верификацию.'),
              open_button(_('Открыть никях')))
        return
    if p.verified:
        reply(tg_id, _('Вы уже верифицированы ✅'))
        return
    if not msg.get('video_note'):
        reply(tg_id, _('Нужен именно видео-кружок (не обычное видео). Нажмите 🎤, чтобы он сменился на 📹, и удерживайте.'))
        return
    chat = moderation_chat()
    if not chat:
        reply(tg_id, _('Верификация временно недоступна — попробуйте позже.'))
        return
    api('copyMessage', {'chat_id': chat, 'from_chat_id': tg_id, 'message_id': msg['message_id'],
                        'protect_content': 'true'})
    kb = {'inline_keyboard': [[{'text': _('✅ Лицо видно, фраза верна'), 'callback_data': f'nk:ver:ok:{p.pk}'}],
                              [{'text': _('❌ Отклонить'), 'callback_data': f'nk:ver:no:{p.pk}'}]]}
    api('sendMessage', {'chat_id': chat, 'reply_markup': kb,
                        'text': _('🎥 Верификация анкеты #{v1}: должен(на) сказать «{v3}, {v5}»').format(v1=p.pk, v3=p.display_name, v5=p.age)})
    cache.delete(f'nkverify:{tg_id}')
    reply(tg_id, _('Спасибо! Кружок отправлен модератору — обычно проверяем в течение суток.'))


# ---------- кнопки модераторов ----------

def callback(cq: dict) -> str:
    """nk:mod:ok:<id> / nk:mod:no / nk:ver:ok / nk:ver:no. Возвращает текст всплывашки."""
    from apps.accounts.models import AuditLog

    from .services import notify

    if not is_moderator(cq):
        return _('Нет прав модератора')
    try:
        _nk, kind, verdict, pk = cq['data'].split(':')
        p = NikahProfile.objects.get(pk=int(pk))
    except (ValueError, NikahProfile.DoesNotExist):
        return _('Анкета не найдена')
    who = cq['from'].get('username') or cq['from'].get('first_name') or cq['from']['id']
    if kind == 'mod':
        (approve if verdict == 'ok' else reject)(p)
        result = _('✅ Одобрено') if verdict == 'ok' else _('❌ Отклонено')
    else:
        if verdict == 'ok':
            p.verified, p.verified_at = True, timezone.now()
            p.save(update_fields=['verified', 'verified_at'])
            notify(p, _lazy('Верификация пройдена — на анкете значок ✅'), '/nikah/me/')
        else:
            notify(p, _lazy('Верификация не пройдена: на кружке должно быть видно лицо и слышна фраза. Попробуйте ещё раз.'),
                   '/nikah/settings/')
        result = _('✅ Верифицирован') if verdict == 'ok' else _('❌ Верификация отклонена')
    AuditLog.objects.create(action=f'Никях (Telegram): {result}', target=f'анкета #{p.pk}, модератор @{who}')
    m = cq.get('message', {})
    api('editMessageText', {'chat_id': m.get('chat', {}).get('id'), 'message_id': m.get('message_id'),
                            'text': (m.get('text') or '')[:3800] + f'\n\n{result} — @{who}'})
    return result
