#!/bin/sh
# Старт контейнера ilm4 в проде: миграции, статика, ASGI-сервер (страницы + WebSocket: чат, звонки).
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput
# Telegram-бот: кнопка «Никях» и вебхук на SITE_URL (если бот настроен; ошибка не мешает старту сайта)
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_WEBHOOK_SECRET:-}" ]; then
  python manage.py tg_setup --webhook || echo "tg_setup: не удалось, проверьте TELEGRAM_* и SITE_URL"
fi

# uvicorn: несколько рабочих процессов (WEB_WORKERS, по умолчанию 3). Один завис или упал —
# остальные продолжают отвечать, а упавший перезапускается сам. Каждый процесс перезапускается
# после 20 000 запросов — память не «утекает» неделями. Общие данные между процессами — в Redis.
# Запасной вариант — прежний сервер в один процесс: ASGI_SERVER=daphne в .env.
if [ "${ASGI_SERVER:-uvicorn}" = "daphne" ]; then
  exec daphne -b 0.0.0.0 -p 8000 --proxy-headers config.asgi:application
fi
exec uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --workers "${WEB_WORKERS:-3}" \
  --proxy-headers --forwarded-allow-ips='*' --no-server-header --timeout-keep-alive 65 \
  --limit-max-requests 20000 --timeout-graceful-shutdown 20
