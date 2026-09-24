"""Каталог сервисов: группы и короткие описания для экрана «Все сервисы».

Сервисы (разделы) берутся из ModuleConfig — порядок и статус задаются в админке.
Здесь только группировка и подписи. Новый раздел без группы попадает в «Ещё»,
без описания — показывается просто по названию: ничего не ломается при 30+ разделах.
"""
from dataclasses import dataclass, field

from django.utils.translation import gettext_lazy as _lazy

# (ключ группы, название, ключи разделов по порядку показа внутри группы)
GROUPS = [
    ('faith', _lazy('Вера и знания'), ['prayer', 'learn', 'library', 'forum', 'news']),
    ('shop', _lazy('Покупки и деньги'), ['buy', 'services', 'finance', 'invest', 'digital', 'wallet']),
    ('life', _lazy('Жизнь и семья'), ['map', 'health', 'nikah', 'realestate', 'sport', 'fun']),
    ('move', _lazy('Работа, переезд и право'), ['jobs', 'migration', 'transport', 'refugee', 'lawyers']),
    ('talk', _lazy('Общение'), ['chat']),
]
OTHER = ('more', _lazy('Ещё'))

DESCR = {
    'prayer': _lazy('Точное время намаза по городу или GPS'),
    'learn': _lazy('Арабский, английский и другие языки'),
    'library': _lazy('Книги по акыде, фикху, истории'),
    'forum': _lazy('Вопросы и ответы уммы'),
    'news': _lazy('Главное из исламского мира'),
    'buy': _lazy('Халяль-маркетплейс: покупай и продавай'),
    'services': _lazy('Переводы, юристы, туры хадж и умра'),
    'finance': _lazy('Исламские финансы без рибы'),
    'invest': _lazy('Халяль-инвестиции и партнёрства'),
    'digital': _lazy('Цифровые услуги и фриланс'),
    'wallet': _lazy('Баланс и история операций'),
    'map': _lazy('Кафе, магазины и отели рядом'),
    'health': _lazy('Врачи уммы по городам'),
    'nikah': _lazy('Знакомства для брака — серьёзно'),
    'realestate': _lazy('Аренда и продажа жилья'),
    'sport': _lazy('Секции, залы и команды'),
    'jobs': _lazy('Вакансии от честных работодателей'),
    'migration': _lazy('Реальные истории переезда'),
    'transport': _lazy('Грузы, пассажиры, попутчики'),
    'refugee': _lazy('УВКБ ООН, посольства, организации'),
    'chat': _lazy('Личные сообщения'),
    'lawyers': _lazy('Юридическая помощь, адвокаты по странам'),
    'fun': _lazy('Халяль-досуг: события, отдых, игры'),
}


@dataclass
class Extra:
    """Пункт каталога, который не раздел (страница-руководство или внешний сервис)."""
    key: str
    name: str
    url: str
    ui_icon: str
    descr: str = ''
    status: str = 'on'
    external: bool = False


# встраиваются в группу по её ключу (в начало), видны и в поиске каталога
EXTRAS = {
    'faith': [
        Extra('shahada', _lazy('Как принять ислам'), '/islam/', 'star', _lazy('Шахада, первые шаги, ответы на вопросы')),
        Extra('salah', _lazy('Как совершать намаз'), '/salah/', 'clock', _lazy('Омовение, ракааты и порядок молитвы')),
        Extra('mosque', _lazy('Мечеть рядом'), 'https://www.google.com/maps/search/?api=1&query=mosque', 'pin',
              _lazy('Откроем карту с мечетями поблизости'), external=True),
    ],
    'talk': [
        Extra('feed', _lazy('Лента · бета'), '/feed/', 'play', _lazy('Вертикальная лента: новости, объявления, вопросы')),
    ],
    'more': [
        Extra('settings', _lazy('Настройки и оформление'), '/settings/', 'edit', _lazy('Светлая или тёмная тема, цвет оформления')),
    ],
}


@dataclass
class Group:
    key: str
    name: str
    items: list = field(default_factory=list)


def build_catalog(modules):
    """Разложить разделы по группам. Внутри группы: работающие → «скоро»."""
    by_key = {m.key: m for m in modules}
    groups = []
    used = set()
    for key, name, keys in GROUPS:
        g = Group(key, name, [by_key[k] for k in keys if k in by_key])
        used.update(m.key for m in g.items)
        if g.items:
            groups.append(g)
    rest = [m for m in modules if m.key not in used]
    groups.append(Group(OTHER[0], OTHER[1], rest))  # «Ещё» — всегда: там настройки
    for g in groups:
        g.items.sort(key=lambda m: m.status != 'on')
        for m in g.items:
            m.descr = DESCR.get(m.key, '')
        g.items = EXTRAS.get(g.key, []) + g.items
    return groups
