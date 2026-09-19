# Одноразовый: вставляет section-hero в шапки всех разделов (редизайн v2).
# Запуск из корня проекта: python3 scripts/insert_hero.py
from pathlib import Path

BASE = Path.cwd()

SECTIONS = [
    ("apps/market/templates/market/list.html", "🛒", "ilmbuy — купля-продажа",
     "Халяль-маркетплейс уммы: от телефонов до фиников, от своих — для своих",
     "buy", "Подать объявление", "/buy/add/"),
    ("apps/maps/templates/maps/map.html", "🗺️", "Карта халяль",
     "Кафе, магазины, отели и врачи — на одной карте, рядом с вами",
     "map", "Добавить место", "/map/add/"),
    ("apps/health/templates/health/index.html", "🩺", "Здоровье",
     "Врачи нашей уммы по городам — контакты, опыт, специализации",
     "health", "Публикация врача", "/health/add/"),
    ("apps/news/templates/news/list.html", "📰", "Новости",
     "Главное из исламского мира — коротко и по делу", "news", "", ""),
    ("apps/forum/templates/forum/list.html", "💬", "Форум",
     "Задай вопрос — получи ответ. Знания с пониманием, сообща",
     "forum", "Задать вопрос", "/forum/ask/"),
    ("apps/jobs/templates/jobs/list.html", "💼", "Работа",
     "Вакансии от своих: честные работодатели, без серых схем",
     "jobs", "Добавить вакансию", "/jobs/add/"),
    ("apps/migration/templates/migration/list.html", "✈️", "Миграция",
     "Реальные истории переезда: визы, работа, жильё, ошибки и находки",
     "migration", "Рассказать свою", "/migration/add/"),
    ("apps/services/templates/services/list.html", "📄", "Услуги",
     "Нотариальные переводы, исламские юристы, туры хадж и умра",
     "services", "Предложить услугу", "/services/add/"),
    ("apps/library/templates/library/list.html", "📚", "Библиотека",
     "Книги для роста: бесплатные и платные, с мгновенным доступом",
     "library", "Добавить книгу", "/library/add/"),
    ("apps/nikah/templates/nikah/list.html", "💍", "Никах",
     "Знакомства для брака — серьёзно, с модерацией анкет",
     "nikah", "Создать анкету", "/nikah/create/"),
    ("apps/prayer/templates/prayer/index.html", "🕌", "Время намаза",
     "Точный расчёт по вашему городу или GPS — быстро и без приложений",
     "prayer", "", ""),
    ("apps/wallet/templates/wallet/index.html", "💰", "Кошелёк",
     "Ваш баланс и история операций платформы", "wallet", "", ""),
    ("apps/chat/templates/chat/inbox.html", "💬", "Сообщения",
     "Диалоги по объявлениям и услугам — в реальном времени",
     "chat", "Новый диалог", "/chat/start/"),
]

MARKER = "{% block content %}"

for rel, icon, title, desc, cls, cta, cta_url in SECTIONS:
    path = BASE / rel
    html = path.read_text(encoding="utf-8")
    if "section_hero" in html:
        print("skip (уже есть):", rel)
        continue
    if MARKER not in html:
        print("НЕТ МАРКЕРА:", rel)
        continue
    hero = ("{% include 'includes/section_hero.html' with "
            f'icon="{icon}" title="{title}" desc="{desc}" class="{cls}"')
    if cta:
        hero += f' cta="{cta}" cta_url="{cta_url}"'
    hero += " %}"
    html = html.replace(MARKER, MARKER + "\n" + hero, 1)
    path.write_text(html, encoding="utf-8")
    print("ok:", rel)
print("DONE")
