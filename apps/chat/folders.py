"""Свой порядок в списке чатов — как в Telegram: папки, архив, закреп, «не прочитано», черновик, очистка истории.

Всё здесь — личное: у каждого человека свои папки и своё состояние чата (ChatState). Собеседник
этого не видит. Снаружи функции зовут через services.py.

Папка (ChatFolder) собирается по правилам, как в Telegram:
* типы чатов (личные, по объявлениям, никях, группы, каналы) — входят все чаты такого типа;
* «всегда включать» — конкретные чаты, даже если тип не выбран;
* «всегда исключать» — конкретные чаты;
* исключить «без звука», прочитанные, архивные.
Вкладка «Все» есть всегда: в ней всё, кроме архива. Архив — отдельной строкой сверху.
"""
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from .models import ChatFolder, ChatState, Thread

PIN_LIMIT = 5                      # закреплённых в общем списке — как в Telegram
TYPE_KEYS = {k for k, _name in ChatFolder.TYPES}

# готовые папки, которые можно добавить одним нажатием («Рекомендованные папки» в Telegram)
RECOMMENDED = [
    {'key': 'unread', 'title': _lazy('Новые'), 'emoji': '', 'hint': _lazy('Только чаты с непрочитанными сообщениями'),
     'types': ['personal', 'ads', 'nikah', 'groups', 'channels'], 'no_read': True},
    {'key': 'personal', 'title': _lazy('Личные'), 'emoji': '', 'hint': _lazy('Переписка с людьми, без групп и каналов'),
     'types': ['personal']},
    {'key': 'ads', 'title': _lazy('Объявления'), 'emoji': '', 'hint': _lazy('Чаты с продавцами, покупателями, работодателями'),
     'types': ['ads']},
    {'key': 'rooms', 'title': _lazy('Сообщества'), 'emoji': '', 'hint': _lazy('Группы и каналы'),
     'types': ['groups', 'channels']},
]


def _error(text, status=400):
    from .services import ChatError
    return ChatError(text, status)


# ---------- состояние чата ----------

def state_of(thread, user, create: bool = False):
    if create:
        return ChatState.objects.get_or_create(thread=thread, user=user)[0]
    return ChatState.objects.filter(thread=thread, user=user).first()


def _mine(thread, user) -> None:
    """Состояние можно менять только у чата, в котором человек состоит."""
    from .services import is_participant
    if not is_participant(thread, user):
        raise _error(_('Нет доступа'), 403)


def set_pinned(thread, user, on: bool, folder=None) -> None:
    """Закрепить чат вверху списка. В общем списке — до 5 чатов; в своей папке — сколько угодно (как в Telegram)."""
    _mine(thread, user)
    if folder is not None:
        pins = [pk for pk in folder.pins if pk != thread.pk]
        if on:
            pins.insert(0, thread.pk)
        folder.pins = pins[:ChatFolder.MAX_CHATS]
        folder.save(update_fields=['pins'])
        return
    st = state_of(thread, user, create=True)
    if on and not st.pinned_at:
        same = ChatState.objects.filter(user=user, pinned_at__isnull=False, archived=st.archived).count()
        if same >= PIN_LIMIT:
            raise _error(_('Закрепить можно не больше {v1} чатов. Открепите один — или закрепляйте в своих папках, '
                           'там ограничения нет.').format(v1=PIN_LIMIT))
    st.pinned_at = timezone.now() if on else None
    st.save(update_fields=['pinned_at'])


def set_archived(thread, user, on: bool) -> None:
    """В архив / из архива. Чат из архива вернётся сам, когда придёт сообщение, — если он не «без звука»."""
    _mine(thread, user)
    st = state_of(thread, user, create=True)
    st.archived = bool(on)
    st.pinned_at = None
    st.save(update_fields=['archived', 'pinned_at'])


def set_unread(thread, user, on: bool) -> None:
    """«Пометить как непрочитанное» / «прочитанное»."""
    from . import services
    _mine(thread, user)
    if not on:
        services.mark_read(thread, user)
        return
    st = state_of(thread, user, create=True)
    st.unread_mark = True
    st.save(update_fields=['unread_mark'])


def set_draft(thread, user, text: str) -> None:
    """Черновик — недописанное сообщение; хранится зашифрованным и виден на всех устройствах человека."""
    from . import services
    from .keyring import encrypt_text
    if not services.can_read(thread, user):
        raise _error(_('Нет доступа'), 403)
    text = (text or '').strip()[:services.MAX_TEXT]
    st = state_of(thread, user, create=bool(text))
    if st is None:
        return
    st.draft_enc = encrypt_text(thread.pk, text) if text else ''
    st.save(update_fields=['draft_enc'])


def clear_history(thread, user) -> None:
    """«Очистить историю» у себя: всё, что было до этого момента, человек больше не видит. У собеседника — остаётся."""
    _mine(thread, user)
    st = state_of(thread, user, create=True)
    st.cleared_at = timezone.now()
    st.unread_mark = False
    st.draft_enc = ''
    st.save(update_fields=['cleared_at', 'unread_mark', 'draft_enc'])


def hide_chat(thread, user) -> None:
    """«Удалить чат» у себя (личный диалог): история очищается, чат пропадает из списка.
    Напишет собеседник — чат появится снова, с новыми сообщениями."""
    _mine(thread, user)
    if thread.is_room:
        raise _error(_('Из группы или канала нужно выйти — кнопка «Выйти» в сведениях.'))
    st = state_of(thread, user, create=True)
    st.cleared_at = timezone.now()
    st.hidden, st.archived, st.pinned_at, st.unread_mark, st.draft_enc = True, False, None, False, ''
    st.save()
    for f in ChatFolder.objects.filter(user=user):
        f.include.remove(thread)
        f.exclude.remove(thread)


# ---------- папки ----------

def user_folders(user) -> list:
    return list(ChatFolder.objects.filter(user=user).prefetch_related('include', 'exclude'))


def _clean_types(value) -> list:
    if isinstance(value, str):
        value = [v for v in value.split(',') if v]
    return [k for k in dict.fromkeys(value or []) if k in TYPE_KEYS]


def _flag(data, key, default=False) -> bool:
    if key not in data:
        return default
    return str(data[key]).lower() in ('1', 'true', 'on', 'yes')


def _ids(value) -> list:
    if isinstance(value, str):
        value = value.split(',')
    out = []
    for v in value or []:
        try:
            out.append(int(v))
        except (TypeError, ValueError):
            continue
    return out


def save_folder(user, data, folder=None) -> ChatFolder:
    """Создать или изменить папку. data: title, emoji, types[], no_muted, no_read, no_archived, include[], exclude[]."""
    title = str(data.get('title', folder.title if folder else '')).strip()[:24]
    if not title:
        raise _error(_('Дайте папке название.'))
    if folder is None:
        if ChatFolder.objects.filter(user=user).count() >= ChatFolder.MAX_FOLDERS:
            raise _error(_('Можно создать не больше {v1} папок.').format(v1=ChatFolder.MAX_FOLDERS))
        last = ChatFolder.objects.filter(user=user).order_by('-order').values_list('order', flat=True).first()
        folder = ChatFolder(user=user, order=(last or 0) + 1)
    folder.title = title
    if 'emoji' in data:
        folder.emoji = str(data.get('emoji') or '').strip()[:8]
    if 'types' in data:
        folder.types = _clean_types(data.get('types'))
    folder.no_muted = _flag(data, 'no_muted', folder.no_muted)
    folder.no_read = _flag(data, 'no_read', folder.no_read)
    folder.no_archived = _flag(data, 'no_archived', folder.no_archived)
    include = _ids(data.get('include')) if 'include' in data else None
    exclude = _ids(data.get('exclude')) if 'exclude' in data else None
    if not folder.types and include is not None and not include:
        raise _error(_('В папке пока пусто: выберите типы чатов или добавьте чаты.'))
    if not folder.types and include is None and (folder.pk is None or not folder.include.exists()):
        raise _error(_('В папке пока пусто: выберите типы чатов или добавьте чаты.'))
    with transaction.atomic():
        folder.save()
        mine = set(user.chat_threads.values_list('pk', flat=True))
        if include is not None:
            folder.include.set([pk for pk in include if pk in mine][:ChatFolder.MAX_CHATS])
        if exclude is not None:
            folder.exclude.set([pk for pk in exclude if pk in mine][:ChatFolder.MAX_CHATS])
        folder.pins = [pk for pk in folder.pins if pk in mine]
        folder.save(update_fields=['pins'])
    return folder


def delete_folder(user, folder_id) -> None:
    """Удалить папку. Сами чаты остаются — пропадает только вкладка."""
    ChatFolder.objects.filter(user=user, pk=folder_id).delete()


def reorder_folders(user, ids) -> None:
    """Свой порядок вкладок: ids — папки в нужном порядке."""
    mine = {f.pk: f for f in ChatFolder.objects.filter(user=user)}
    order = [pk for pk in _ids(ids) if pk in mine]
    order += [pk for pk in mine if pk not in order]
    for i, pk in enumerate(order):
        if mine[pk].order != i:
            ChatFolder.objects.filter(pk=pk).update(order=i)


def set_folder_chat(user, folder_id, thread, on: bool) -> None:
    """Добавить чат в папку / убрать из неё (долгое нажатие на чат → «Добавить в папку»)."""
    _mine(thread, user)
    folder = ChatFolder.objects.filter(user=user, pk=folder_id).first()
    if folder is None:
        raise _error(_('Папка не найдена'), 404)
    if on:
        if folder.include.count() >= ChatFolder.MAX_CHATS:
            raise _error(_('В папке не больше {v1} выбранных чатов.').format(v1=ChatFolder.MAX_CHATS))
        folder.include.add(thread)
        folder.exclude.remove(thread)
    else:
        folder.include.remove(thread)
        if thread.chat_type in folder.types:           # чат попадает в папку по типу — исключаем поимённо
            folder.exclude.add(thread)


def recommended_folders(user) -> list:
    """Готовые папки, которых у человека ещё нет (по названию)."""
    have = {f.title.lower() for f in ChatFolder.objects.filter(user=user)}
    return [{**r, 'title': str(r['title']), 'hint': str(r['hint'])} for r in RECOMMENDED
            if str(r['title']).lower() not in have]


def _match(folder, t, inc: set, exc: set) -> bool:
    if t.pk in exc:
        return False
    if t.pk in inc:
        return True
    if t.chat_type not in folder.types:
        return False
    if folder.no_muted and t.muted:
        return False
    if folder.no_read and not (t.unread or t.unread_mark):
        return False
    return not (folder.no_archived and t.archived)


def folder_summary(user, threads) -> dict:
    """Вкладки для списка чатов. threads — чаты из services.inbox (с .unread, .muted, .archived…).

    Возвращает {'folders': [{id, title, emoji, ids, pins, n, unread, unread_muted, …}], 'archive': {…}, 'all': {…}}.
    unread — сколько чатов с непрочитанным (не сообщений): так считает Telegram на вкладках.
    """
    def count(rows):
        loud = sum(1 for t in rows if (t.unread or t.unread_mark) and not t.muted)
        quiet = sum(1 for t in rows if (t.unread or t.unread_mark) and t.muted)
        return {'n': len(rows), 'unread': loud, 'unread_muted': quiet}

    main = [t for t in threads if not t.archived]
    archived = [t for t in threads if t.archived]
    out = []
    for f in user_folders(user):
        inc = {t.pk for t in f.include.all()}
        exc = {t.pk for t in f.exclude.all()}
        rows = [t for t in threads if _match(f, t, inc, exc)]
        ids = {t.pk for t in rows}
        out.append({'id': f.pk, 'title': f.title, 'emoji': f.emoji, 'types': f.types, 'no_muted': f.no_muted,
                    'no_read': f.no_read, 'no_archived': f.no_archived, 'include': sorted(inc), 'exclude': sorted(exc),
                    'ids': [t.pk for t in rows], 'pins': [pk for pk in f.pins if pk in ids], **count(rows)})
    return {'folders': out, 'all': {'ids': [t.pk for t in main], **count(main)},
            'archive': {'ids': [t.pk for t in archived], **count(archived),
                        'names': [getattr(t, 'list_name', '') for t in archived[:4]]}}


def folder_types() -> list:
    """Типы чатов для настройки папки. «Боты» появятся, когда появятся сами боты."""
    return [{'key': k, 'name': str(name)} for k, name in ChatFolder.TYPES if k != 'bots']


def unarchive_all_on_leave(thread, user) -> None:
    """Вышел из группы или канала — личное состояние больше не нужно."""
    ChatState.objects.filter(thread=thread, user=user).delete()
    for f in ChatFolder.objects.filter(user=user):
        f.include.remove(thread)
        f.exclude.remove(thread)


__all__ = [
    'Thread',
    'clear_history',
    'delete_folder',
    'folder_summary',
    'folder_types',
    'hide_chat',
    'recommended_folders',
    'reorder_folders',
    'save_folder',
    'set_archived',
    'set_draft',
    'set_folder_chat',
    'set_pinned',
    'set_unread',
    'state_of',
    'user_folders',
]
