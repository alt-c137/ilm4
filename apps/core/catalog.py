"""Каталог сервисов: группы и короткие описания для экрана «Все сервисы».

Сервисы (разделы) берутся из ModuleConfig — порядок и статус задаются в админке.
Здесь только группировка и подписи. Новый раздел без группы попадает в «Ещё»,
без описания — показывается просто по названию: ничего не ломается при 30+ разделах.
"""
from dataclasses import dataclass, field

# (ключ группы, название, ключи разделов по порядку показа внутри группы)
GROUPS = [
    ('faith', 'Вера и знания', ['prayer', 'learn', 'library', 'forum', 'news']),
    ('shop', 'Покупки и деньги', ['buy', 'services', 'finance', 'invest', 'digital', 'wallet']),
    ('life', 'Жизнь и семья', ['map', 'health', 'nikah', 'realestate', 'sport', 'fun']),
    ('move', 'Работа, переезд и право', ['jobs', 'migration', 'transport', 'refugee', 'lawyers']),
    ('talk', 'Общение', ['chat']),
]
OTHER = ('more', 'Ещё')

DESCR = {
    'prayer': 'Точное время намаза по городу или GPS',
    'learn': 'Арабский, английский и другие языки',
    'library': 'Книги по акыде, фикху, истории',
    'forum': 'Вопросы и ответы уммы',
    'news': 'Главное из исламского мира',
    'buy': 'Халяль-маркетплейс: покупай и продавай',
    'services': 'Переводы, юристы, туры хадж и умра',
    'finance': 'Исламские финансы без рибы',
    'invest': 'Халяль-инвестиции и партнёрства',
    'digital': 'Цифровые услуги и фриланс',
    'wallet': 'Баланс и история операций',
    'map': 'Кафе, магазины и отели рядом',
    'health': 'Врачи уммы по городам',
    'nikah': 'Знакомства для брака — серьёзно',
    'realestate': 'Аренда и продажа жилья',
    'sport': 'Секции, залы и команды',
    'jobs': 'Вакансии от честных работодателей',
    'migration': 'Реальные истории переезда',
    'transport': 'Грузы, пассажиры, попутчики',
    'refugee': 'УВКБ ООН, посольства, организации',
    'chat': 'Личные сообщения',
    'lawyers': 'Юридическая помощь, адвокаты по странам',
    'fun': 'Халяль-досуг: события, отдых, игры',
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
        Extra('shahada', 'Как принять ислам', '/islam/', 'star', 'Шахада, первые шаги, ответы на вопросы'),
        Extra('salah', 'Как совершать намаз', '/salah/', 'clock', 'Омовение, ракааты и порядок молитвы'),
        Extra('mosque', 'Мечеть рядом', 'https://www.google.com/maps/search/?api=1&query=mosque', 'pin',
              'Откроем карту с мечетями поблизости', external=True),
    ],
    'talk': [
        Extra('feed', 'Лента · бета', '/feed/', 'play', 'Вертикальная лента: новости, объявления, вопросы'),
    ],
    'more': [
        Extra('settings', 'Настройки и оформление', '/settings/', 'edit', 'Светлая или тёмная тема, цвет оформления'),
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
