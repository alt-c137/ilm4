"""Нижние кнопки (вкладки) — каждый выбирает свои: «Сервисы» поменять на «Карту», «Намаз» на «Трекер» и т. д.

Сайт и приложение хранят выбор отдельно (экраны разные): User.ui = {'tabs_site': […], 'tabs_app': […]}.
Последняя кнопка — «Профиль» — всегда на месте: через неё попадают в настройки.
Новый раздел добавляется одной строкой в TABS — и сразу доступен для выбора.
"""
from django.utils.translation import gettext_lazy as _lazy

# ключ → (подпись, адрес на сайте, ключ раздела ModuleConfig или '', значок 24×24 — содержимое <svg>)
TABS = {
    'home': (_lazy('Главная'), '/', '', '<path d="M3.5 10.5 12 3.5l8.5 7V19a1.5 1.5 0 0 1-1.5 1.5h-4v-6h-6v6H5A1.5 1.5 0 0 1 3.5 19z"/>'),
    'services': (_lazy('Сервисы'), '/catalog/', '', '<rect x="4" y="4" width="6.5" height="6.5" rx="2"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="2"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="2"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="3.25"/>'),
    'add': (_lazy('Подать'), '/buy/add/', 'buy', '<path d="M12 5v14M5 12h14"/>'),
    'chats': (_lazy('Чаты'), '/chat/', 'chat', '<path d="M20.5 11.5a8 8 0 0 1-11.4 7.2L3.5 20.5l1.8-5.5a8 8 0 1 1 15.2-3.5z"/>'),
    'prayer': (_lazy('Намаз'), '/prayer/', 'prayer', '<path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5z"/>'),
    'tracker': (_lazy('Трекер'), '/tracker/', 'tracker', '<circle cx="12" cy="12" r="8.5"/><path d="M8.3 12.3l2.5 2.4 4.9-5.2"/>'),
    'nikah': (_lazy('Никях'), '/nikah/', 'nikah', '<path d="M12 20s-7-4.5-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.5-7 10-7 10z"/>'),
    'map': (_lazy('Карта'), '/map/', 'map', '<path d="M12 21s-6.5-5.3-6.5-10a6.5 6.5 0 0 1 13 0c0 4.7-6.5 10-6.5 10z"/><circle cx="12" cy="10.6" r="2.3"/>'),
    'buy': (_lazy('Маркет'), '/buy/', 'buy', '<path d="M5 8h14l-1.2 11.5H6.2zM9 8V6.5a3 3 0 0 1 6 0V8"/>'),
    'jobs': (_lazy('Работа'), '/jobs/', 'jobs', '<rect x="3.5" y="7.5" width="17" height="12" rx="2"/><path d="M9 7.5V5.5h6v2M3.5 12.5h17"/>'),
    'news': (_lazy('Новости'), '/news/', 'news', '<path d="M4 5h13v14H5a1 1 0 0 1-1-1zM17 9h3v9a1 1 0 0 1-3 0M7.5 9h6M7.5 12.5h6M7.5 16h4"/>'),
    'forum': (_lazy('Форум'), '/forum/', 'forum', '<path d="M4 5h11v8H9l-3 3v-3H4zM15 9h5v8h-2v3l-3-3h-4v-2"/>'),
    'feed': (_lazy('Лента'), '/feed/', 'feed', '<path d="M4 5.5h16M4 12h16M4 18.5h10"/>'),
    'communities': (_lazy('Сообщества'), '/communities/', 'communities', '<circle cx="9" cy="8.5" r="3.5"/><path d="M2.5 20c.9-3.3 3.4-5 6.5-5s5.6 1.7 6.5 5M16 5.2a3.5 3.5 0 0 1 0 6.6M18 15.3c1.7.7 2.9 2.2 3.5 4.7"/>'),
    'library': (_lazy('Книги'), '/library/', 'library', '<path d="M5 4.5h4v15H5zM10 4.5h4v15h-4zM15.5 5l3.6-.9 3 14.6-3.6.9z"/>'),
    'transport': (_lazy('Попутчики'), '/transport/', 'transport', '<path d="M5 16V11l1.8-4.5h10.4L19 11v5M5 16h14M5 16v2.5M19 16v2.5M5 11h14"/><circle cx="8" cy="13.6" r=".6"/><circle cx="16" cy="13.6" r=".6"/>'),
}
SLOTS = 20                         # сколько угодно: больше пяти — панель листается пальцем (как человеку удобно)
DEFAULT_SITE = ['home', 'services', 'add', 'chats']
DEFAULT_APP = ['home', 'prayer', 'services', 'chats']
APP_KEYS = [k for k in TABS if k != 'add']      # экраны-вкладки, которые есть в приложении («Подать» — только на сайте)


def _clean_list(value, allowed) -> list | None:
    if not isinstance(value, list):
        return None
    out = []
    for key in value:
        if isinstance(key, str) and key in allowed and key not in out:
            out.append(key)
    return out[:SLOTS] if len(out) >= 2 else None


def clean_ui(data: dict) -> dict:
    """Из присланных настроек интерфейса берём только известное (чужой мусор в профиль не попадёт)."""
    out = {}
    site = _clean_list(data.get('tabs_site'), TABS)
    app = _clean_list(data.get('tabs_app'), APP_KEYS)
    if site:
        out['tabs_site'] = site
    if app:
        out['tabs_app'] = app
    if data.get('links_view') in ('auto', 'pills', 'icons', 'list'):       # как показывать соцсети в профиле
        out['links_view'] = data['links_view']
    if data.get('start') in START:                  # с какого раздела открывается ilm4: платформа целиком или, например, только чаты
        out['start'] = data['start']
    return out


START = [k for k in TABS if k not in ('home', 'add', 'services')]


def start_url(user, modules_on: set) -> str:
    """Куда вести с «/», если человек выбрал другой стартовый экран. Пусто — обычная главная."""
    if not getattr(user, 'is_authenticated', False):
        return ''
    ui = getattr(user, 'ui', None) or {}
    if 'start' in ui or 'tabs_site' in ui or 'desk' in ui:       # человек выбирал сам (в том числе «главная»)
        key = ui.get('start')
    else:
        from . import desks
        key = desks.preset(user)['start']
    if key in START and (not TABS[key][2] or TABS[key][2] in modules_on):
        return TABS[key][1]
    return ''


def site_tabs(user, modules_on: set, path: str, is_home: bool) -> list:
    """Кнопки нижней панели сайта для этого человека (выключенные в админке разделы пропускаются)."""
    from . import desks
    chosen = (getattr(user, 'ui', None) or {}).get('tabs_site') if getattr(user, 'is_authenticated', False) else None
    chosen = chosen or desks.preset(user)['tabs_site']            # сам не выбирал — кнопки рабочего стола (свой или тот, что задал владелец)
    keys = [k for k in chosen if k in TABS and (not TABS[k][2] or TABS[k][2] in modules_on)]
    if len(keys) < 2:
        keys = [k for k in DEFAULT_SITE if not TABS[k][2] or TABS[k][2] in modules_on]
    out = []
    for k in keys:
        label, url, _module, icon = TABS[k]
        on = is_home if k == 'home' else (path.startswith(url) and k != 'add') or (k == 'add' and path == url)
        out.append({'key': k, 'label': label, 'url': url, 'icon': icon, 'on': on})
    # «Маркет» и «Подать» оба начинаются с /buy/: подсветка только у точного совпадения
    if sum(1 for t in out if t['on']) > 1:
        best = max((t for t in out if t['on']), key=lambda t: len(t['url']))
        for t in out:
            t['on'] = t is best
    return out


def side_nav(user, modules, path: str, is_home: bool) -> dict:
    """Боковое меню для широкого экрана (как у ВК и X): сверху — разделы, которые человек сам держит под рукой
    (те же, что в нижних кнопках), ниже — остальные включённые разделы."""
    on = {m.key for m in modules}
    main = [t for t in site_tabs(user, on, path, is_home) if t['key'] not in ('add', 'services')]    # «Все сервисы» в меню есть всегда
    taken = {TABS[t['key']][2] for t in main if TABS[t['key']][2]}
    rest = [{'key': m.key, 'label': m.name, 'url': f'/{m.key}/', 'icon_key': m.key, 'icon': m.icon, 'on': path.startswith(f'/{m.key}/')}
            for m in modules if m.key not in taken and m.key != 'wallet']
    return {'main': main, 'rest': rest}


def choices(modules_on: set, app: bool = False) -> list:
    keys = APP_KEYS if app else list(TABS)
    return [{'key': k, 'label': str(TABS[k][0])} for k in keys if not TABS[k][2] or TABS[k][2] in modules_on]
