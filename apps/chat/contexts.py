"""К чему относится чат: объявление, вакансия, услуга, врач, никях, поддержка (docs/MESSENGER.md §5).

Мессенджер один, но у чата есть «контекст» — раздел и объект. От него зависят:
* папка в списке чатов (Thread.folder);
* карточка вверху чата (фото, название, цена, «снято с публикации», ссылка);
* подсказки и правила: предупреждение о предоплате у продавцов, «не заменяет приём» у врачей,
  кнопка «Отправить резюме» в вакансии, «Безопасная сделка» у продавцов и исполнителей.

Свой чат на каждое объявление: два разговора с одним продавцом о разных товарах не смешиваются.
"""
import re

from django.utils.translation import gettext as _

from apps.core.models import Moderation
from apps.core.publications import BY_KEY

NIKAH, SUPPORT = 'nikah', 'support'
RISKY = {'buy', 'services', 'transport', 'jobs'}        # где встречаются просьбы о предоплате

# «переведи на карту», «предоплата», номер карты, ссылки на оплату — признаки мошенничества
SCAM = re.compile(
    r'предоплат|аванс|задаток|перев(?:еди|едите|од)\w*\s+(?:мне\s+)?(?:на\s+)?карт|номер\s+карт|реквизит|'
    r'oldindan\s+to.?lov|kartaga\s+(?:tashla|o.?tkaz)|prepay|advance\s+payment|card\s+number|western\s+union|'
    r'(?<!\d)(?:\d{4}[ -]?){3}\d{4}(?!\d)', re.IGNORECASE)


def resolve(key: str, obj_id, owner) -> tuple | None:
    """Проверить контекст: раздел существует, объект есть и принадлежит собеседнику.
    Иначе можно было бы открыть чат «по чужому объявлению» с кем угодно."""
    pub = BY_KEY.get(key or '')
    if pub is None or not str(obj_id or '').isdigit():
        return None
    obj = pub.get_model().objects.filter(pk=int(obj_id)).first()
    if obj is None or getattr(obj, f'{pub.owner}_id', None) != owner.pk:
        return None
    return pub, obj


def _price(obj) -> str:
    if getattr(obj, 'price', None) not in (None, ''):
        try:
            if float(obj.price) > 0:
                return f'{int(obj.price):,}'.replace(',', ' ') + ' ' + (getattr(obj, 'currency', '') or '')
        except (TypeError, ValueError):
            pass
    for name in ('price_text', 'salary'):
        if getattr(obj, name, ''):
            return str(getattr(obj, name))
    return ''


def _image(obj) -> str:
    for name in ('photo', 'cover'):
        f = getattr(obj, name, None)
        if f:
            try:
                return f.url
            except ValueError:
                pass
    return ''


def card(thread, user) -> dict | None:
    """Карточка вверху чата. None — обычный личный чат."""
    pub = BY_KEY.get(thread.context_type)
    if pub is None or not thread.context_id:
        return None
    obj = pub.get_model().objects.filter(pk=thread.context_id).first()
    if obj is None:
        return {'title': thread.subject or str(pub.label), 'label': str(pub.label), 'closed': True,
                'closed_text': _('Объявление удалено'), 'url': '', 'price': '', 'image': '', 'actions': []}
    closed = (getattr(obj, 'status', Moderation.APPROVED) != Moderation.APPROVED
              or (pub.active and not getattr(obj, pub.active)))
    mine = getattr(obj, f'{pub.owner}_id', None) == user.pk
    data = {'title': pub.title_of(obj), 'label': str(pub.label), 'price': _price(obj), 'image': _image(obj),
            'url': pub.url_of(obj) if not closed or mine else '', 'closed': closed,
            'closed_text': _('Снято с публикации') if closed else '', 'mine': mine, 'actions': []}
    if thread.context_type == 'jobs' and not mine and not getattr(obj, 'is_resume', False):
        # соискатель в чате по вакансии: отправить своё резюме одним нажатием
        resume = pub.get_model().objects.filter(owner=user, kind='resume', status=Moderation.APPROVED).first()
        if resume:
            data['actions'].append({'kind': 'say', 'label': _('Отправить моё резюме'),
                                    'text': _('Моё резюме: «{title}»').format(title=resume.title) + ' {link}',
                                    'path': pub.url_of(resume)})
    return data


def notice(thread) -> str:
    """Постоянная подсказка под шапкой чата — зависит от раздела."""
    ctx = thread.context_type
    if ctx == 'doctors':
        return _('Переписка не заменяет очный приём врача. В срочных случаях звоните в скорую.')
    if ctx in ('buy', 'services', 'transport'):
        return _('Не переводите предоплату незнакомым людям. Договаривайтесь и платите через «Безопасную сделку» '
                 'или при встрече.')
    if ctx == 'jobs':
        return _('Работодатель не должен просить деньги за трудоустройство, обучение или «оформление».')
    if ctx == SUPPORT:
        return _('Это чат с командой ilm4. Отвечаем по очереди — обычно в течение дня.')
    return ''


def risky(thread) -> bool:
    return thread.context_type in RISKY


def is_scam(body: str) -> bool:
    return bool(body) and bool(SCAM.search(body))


def warn_text() -> str:
    return _('Осторожно: просят предоплату или перевод на карту. ilm4 не возвращает деньги, отправленные мимо '
             '«Безопасной сделки».')
