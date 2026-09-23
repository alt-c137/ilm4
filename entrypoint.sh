#!/bin/sh
# Старт контейнера ilm4 в проде: миграции, статики, ASGI-сервер.
# daphne (ASGI) обслуживает и страницы, и WebSocket (чат, «прочитано», звонки).
# gunicorn (WSGI) WebSocket не умеет — с ним живой чат и звонки не работают.
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec daphne -b 0.0.0.0 -p 8000 --proxy-headers config.asgi:application
