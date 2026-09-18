# ilm4 — веб-платформа

Модульный монолит Django: ядро + разделы (маркетплейс, карта халяль, врачи,
никах, работа и др.). **Документация:** `PASSPORT.md` (что это) и
`ARCHITECTURE.md` (как устроено) — читать перед изменениями.

## Быстрый старт — дев (WSL Ubuntu)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt
python manage.py migrate
python manage.py runserver     # http://127.0.0.1:8000
```

БД по умолчанию SQLite. С Docker Desktop (включить WSL Integration → Ubuntu):
`docker compose up -d`, в `.env` раскомментировать `DATABASE_URL`.

Тесты и проверки: `pytest` · `python manage.py check` · `ruff check .`

## Залить на GitHub

Репозиторий уже с git-историей. У себя на машине с доступом к GitHub:

```bash
# 1. создать пустой репозиторий на github.com (без README/.gitignore — пустой)
# 2. привязать и отправить:
git remote add origin git@github.com:<твой-логин>/ilm4.git   # или https-ссылка
git push -u origin master
```

Секреты не попадут в git: `.env`, база, медиа — в `.gitignore`.

## Установка на сервере (когда будет VPS)

На чистом Ubuntu-сервере с установленными Docker + Docker Compose:

```bash
git clone git@github.com:<твой-логин>/ilm4.git && cd ilm4
cp .env.example .env && nano .env    # вписать: SECRET_KEY, POSTGRES_PASSWORD, ALLOWED_HOSTS
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec app python manage.py createsuperuser
```

Сайт поднимется на `http://<IP-сервера>` — nginx (80) → gunicorn (app) → Postgres.
Обновление версий: `git pull && docker compose -f docker-compose.prod.yml up -d --build`.

## Структура

- `config/` — проект Django (settings: base/dev/prod, urls)
- `apps/core` — настройки сайта, темы, блоки главной, разделы вкл/выкл
- `apps/accounts` — единый User, роли, 2FA админов, журнал действий
- `apps/<раздел>` — по приложению на раздел (появляются по фазам ARCHITECTURE.md §9)
- `templates/`, `static/` — общие шаблоны и дизайн-система «Апп» (tokens.css)
- `Dockerfile`, `docker-compose.prod.yml`, `nginx/` — прод-стек «одна команда»
