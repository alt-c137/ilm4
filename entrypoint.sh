#!/bin/sh
# Старт контейнера ilm4 в проде: миграции, статики, gunicorn.
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 60
