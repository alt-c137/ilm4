#!/bin/sh
# Старт контейнера ilm4 в проде: миграции, статики, ASGI-сервер.
# daphne (ASGI) обслуживает и страницы, и WebSocket (чат, «прочитано», звонки).
# gunicorn (WSGI) WebSocket не умеет — с ним живой чат и звонки не работают.
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput
# Telegram-бот: кнопка «Никях» и вебхук на SITE_URL (если бот настроен; ошибка не мешает старту сайта)
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_WEBHOOK_SECRET:-}" ]; then
  python manage.py tg_setup --webhook || echo "tg_setup: не удалось, проверьте TELEGRAM_* и SITE_URL"
fi

exec daphne -b 0.0.0.0 -p 8000 --proxy-headers config.asgi:application
