# ilm4 — веб-платформа

Модульный монолит Django: ядро + разделы (маркетплейс, карта халяль, врачи,
никах, работа и др.). **Документация:** `PASSPORT.md` (что это) и
`ARCHITECTURE.md` (как устроено) — читать перед изменениями.

## Быстрый старт (WSL Ubuntu)

```bash
# 1. окружение (один раз)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt

# 2. БД: пока не включена Docker-интеграция — SQLite работает из коробки.
#    С Docker Desktop (Settings → Resources → WSL Integration → Ubuntu):
docker compose up -d           # postgres+postgis, redis
cp .env.example .env           # и раскомментируй в .env строку DATABASE_URL=…

# 3. запуск
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver     # http://127.0.0.1:8000
```

## Тесты и проверки

```bash
pytest                         # тесты
python manage.py check         # самопроверка Django
ruff check .                   # линтер
```

## Структура

- `config/` — проект Django (settings: base/dev/prod, urls)
- `apps/core` — настройки сайта, темы, блоки главной, разделы вкл/выкл
- `apps/accounts` — единый User (разворачивается в фазе 1)
- `apps/<раздел>` — по одному приложению на раздел (появляются по фазам)
- `templates/` — общие шаблоны; `static/` — tokens.css/base.css «Апп»
- Разделы разрабатываются по одному за заход — порядок в ARCHITECTURE.md §9
