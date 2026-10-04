"""«Дизайн» и «рабочий стол» — два независимых выбора каждого человека (замысел супер-аппа).

* Дизайн — знакомый интерфейс: как выглядит оболочка (нижняя панель, шапка). «Как сейчас», «как Telegram»,
  «как Авито», «как Instagram», «как X». Содержимое страниц одно и то же — меняется рамка вокруг него.
* Рабочий стол — готовый набор под задачу: какие кнопки внизу, с чего открывается ilm4, какой вид у главной.
  Взял готовый → можно подправить (Настройки → «Нижние кнопки») → он становится «своим».

Что стоит у новых людей по умолчанию, выбирает владелец: Админка → Настройки сайта → «Дизайн / рабочий стол по умолчанию».
Выбор человека хранится в User.ui: {'design': …, 'desk': …} и в самих настройках, которые стол выставляет
(tabs_site, tabs_app, start, home_view) — поэтому «свой стол» ничем не отличается от готового, кроме названия.
"""
from django.utils.translation import gettext_lazy as _lazy

# ключ → (название, пояснение, рекомендуемый стол)
DESIGNS = {
    'classic': (_lazy('ilm4'), _lazy('Как сейчас: кнопки с подписями, «Подать» по центру'), 'all'),
    'telegram': (_lazy('Как Telegram'), _lazy('Плавающая панель-пилюля внизу, чаты на первом месте'), 'talk'),
    'avito': (_lazy('Как Авито'), _lazy('Плоская панель, объявления и поиск на первом месте'), 'market'),
    'insta': (_lazy('Как Instagram'), _lazy('Внизу только значки, в центре — лента'), 'social'),
    'x': (_lazy('Как X'), _lazy('Значки внизу и круглая кнопка «плюс» над ними'), 'social'),
}
DEFAULT_DESIGN = 'classic'

# ключ → набор. tabs — кнопки внизу (сайт / приложение; «Профиль» добавляется сам), start — с чего открывается ilm4
# ('' — главная), home — вид главной (showcase — «Витрина», brief — «Сводка»)
DESKS = {
    'all': {'name': _lazy('Всё сразу'), 'about': _lazy('Главная с сервисами, чаты и объявления — как сейчас'),
            'tabs_site': ['home', 'services', 'add', 'chats'], 'tabs_app': ['home', 'prayer', 'services', 'chats'],
            'start': '', 'home': 'showcase'},
    'talk': {'name': _lazy('Общение'), 'about': _lazy('Чаты, сообщества и лента — как мессенджер'),
             'tabs_site': ['chats', 'communities', 'feed', 'services'], 'tabs_app': ['chats', 'communities', 'feed', 'services'],
             'start': 'chats', 'home': 'brief'},
    'market': {'name': _lazy('Покупки и работа'), 'about': _lazy('Объявления, вакансии, услуги и сообщения по ним'),
               'tabs_site': ['home', 'buy', 'add', 'jobs', 'chats'], 'tabs_app': ['home', 'buy', 'jobs', 'chats'],
               'start': '', 'home': 'showcase'},
    'faith': {'name': _lazy('Вера и привычки'), 'about': _lazy('Намаз, трекер, книги и карта халяль-мест'),
              'tabs_site': ['home', 'prayer', 'tracker', 'map', 'chats'], 'tabs_app': ['home', 'prayer', 'tracker', 'map', 'chats'],
              'start': '', 'home': 'brief'},
    'social': {'name': _lazy('Лента и люди'), 'about': _lazy('Лента, сообщества, новости — как соцсеть'),
               'tabs_site': ['feed', 'communities', 'add', 'news', 'chats'], 'tabs_app': ['feed', 'communities', 'news', 'chats'],
               'start': 'feed', 'home': 'showcase'},
}
DEFAULT_DESK = 'all'
CUSTOM = 'custom'


def site_defaults() -> tuple[str, str]:
    """(дизайн, стол), которые владелец поставил для всех новых людей."""
    from .models import SiteSettings
    st = SiteSettings.get_solo()
    design = st.default_design if st.default_design in DESIGNS else DEFAULT_DESIGN
    desk = st.default_desk if st.default_desk in DESKS else DEFAULT_DESK
    return design, desk


def _ui(user) -> dict:
    return (getattr(user, 'ui', None) or {}) if getattr(user, 'is_authenticated', False) else {}


def design_of(user) -> str:
    key = _ui(user).get('design')
    return key if key in DESIGNS else site_defaults()[0]


def desk_of(user) -> str:
    """Ключ стола человека: готовый, 'custom' (подправил под себя) или стол по умолчанию."""
    ui = _ui(user)
    if ui.get('desk') in DESKS or ui.get('desk') == CUSTOM:
        return ui['desk']
    return CUSTOM if ui.get('tabs_site') else site_defaults()[1]


def preset(user) -> dict:
    """Набор, из которого берутся настройки, если человек сам ничего не менял: его стол или стол по умолчанию."""
    key = desk_of(user)
    return DESKS[key if key in DESKS else site_defaults()[1]]


def apply(user, design: str = '', desk: str = '') -> None:
    """Выбрать дизайн и/или готовый стол. Стол записывает кнопки, старт и вид главной — дальше их можно менять по одной."""
    ui = dict(user.ui or {})
    if design in DESIGNS:
        ui['design'] = design
    if desk in DESKS:
        d = DESKS[desk]
        ui.update({'desk': desk, 'tabs_site': list(d['tabs_site']), 'tabs_app': list(d['tabs_app']), 'home_view': d['home']})
        if d['start']:
            ui['start'] = d['start']
        else:
            ui.pop('start', None)
    ui['welcomed'] = 1
    user.ui = ui
    user.save(update_fields=['ui'])


def touched(ui: dict) -> dict:
    """Человек поменял кнопки или старт вручную — стол теперь «свой»."""
    ui['desk'] = CUSTOM
    return ui


def choices(user, modules_on: set) -> dict:
    """Всё для экрана выбора (сайт и приложение): дизайны и столы с отметкой текущих."""
    from . import tabs
    design, desk = design_of(user), desk_of(user)

    def names(keys):
        return [str(tabs.TABS[k][0]) for k in keys if k in tabs.TABS and (not tabs.TABS[k][2] or tabs.TABS[k][2] in modules_on)]
    return {
        'design': design, 'desk': desk,
        'designs': [{'key': k, 'name': str(v[0]), 'about': str(v[1]), 'desk': v[2], 'on': k == design} for k, v in DESIGNS.items()],
        'desks': [{'key': k, 'name': str(d['name']), 'about': str(d['about']), 'tabs': names(d['tabs_site']), 'on': k == desk}
                  for k, d in DESKS.items()],
        'custom': desk == CUSTOM,
    }
