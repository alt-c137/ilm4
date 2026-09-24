#!/usr/bin/env bash
# Запуск ilm4 на своём ПК «как на сервере» — с https-адресом для Telegram, без ngrok и регистрации.
#
#   bash scripts/run_local.sh
#
# Что делает:
#   1) миграции; 2) сайт на http://127.0.0.1:8000;
#   3) бесплатный туннель Cloudflare → https://<случайное-имя>.trycloudflare.com (адрес меняется при каждом запуске);
#   4) если в .env есть TELEGRAM_BOT_TOKEN — настраивает кнопку «Никях» в боте на этот адрес и запускает бота.
# Остановить всё — Ctrl+C.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=.venv/bin/python
[ -x "$PY" ] || { echo "Нет .venv — сначала: python3 -m venv .venv && .venv/bin/pip install -r requirements/dev.txt"; exit 1; }

# cloudflared — скачиваем один раз в ~/.local/bin (без sudo)
CF=$(command -v cloudflared || echo "$HOME/.local/bin/cloudflared")
if [ ! -x "$CF" ]; then
  echo "Скачиваю cloudflared (один раз)…"
  mkdir -p "$HOME/.local/bin"
  curl -fsSL -o "$HOME/.local/bin/cloudflared" \
    https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
  chmod +x "$HOME/.local/bin/cloudflared"
  CF="$HOME/.local/bin/cloudflared"
fi

LOG=$(mktemp -d)
cleanup() { echo; echo "Останавливаю…"; kill $(jobs -p) 2>/dev/null || true; }
trap cleanup EXIT INT TERM

$PY manage.py migrate --noinput

# https-адрес для Telegram и телефона: сначала Cloudflare, не вышло — localhost.run (тоже без регистрации)
find_url() { grep -oE "$1" "$2" 2>/dev/null | grep -v '//api\.' | head -1 || true; }
URL=""
echo "Запускаю туннель Cloudflare…"
"$CF" tunnel --no-autoupdate --protocol http2 --url http://127.0.0.1:8000 >"$LOG/tunnel.log" 2>&1 &
for _ in $(seq 1 30); do
  URL=$(find_url 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG/tunnel.log")
  [ -n "$URL" ] && break
  sleep 1
done
if [ -z "$URL" ]; then
  echo "Cloudflare не ответил (последние строки лога):"
  tail -n 5 "$LOG/tunnel.log" | sed 's/^/    /'
  echo "Пробую запасной туннель localhost.run…"
  ssh -T -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=30 \
      -o ExitOnForwardFailure=yes -R 80:127.0.0.1:8000 nokey@localhost.run >"$LOG/tunnel2.log" 2>&1 &
  for _ in $(seq 1 30); do
    URL=$(find_url 'https://[a-z0-9-]+\.lhr\.life' "$LOG/tunnel2.log")
    [ -n "$URL" ] && break
    sleep 1
  done
fi
[ -n "$URL" ] || { echo "Туннель не поднялся ни через Cloudflare, ни через localhost.run. Проверьте интернет. Логи: $LOG"; exit 1; }

export SITE_URL="$URL"          # переменная окружения важнее .env — файл не меняем
$PY manage.py runserver 127.0.0.1:8000 >"$LOG/server.log" 2>&1 &
sleep 3

# мобильное приложение (mobile/) на телефоне будет ходить на этот же адрес
echo "EXPO_PUBLIC_API_URL=$URL" > mobile/.env.local

echo
echo "  Сайт:      $URL        (и http://127.0.0.1:8000)"
echo "  Никях:     $URL/nikah/"
echo "  Админка:   $URL/admin/"
echo "  Логи:      $LOG"
echo "  Приложение: во втором окне Ubuntu — bash scripts/run_app.sh (адрес уже прописан)"
echo

if grep -qE '^TELEGRAM_BOT_TOKEN=.+' .env 2>/dev/null; then
  $PY manage.py tg_setup && echo "  В Telegram: откройте бота → кнопка «Никях» слева от поля ввода." && echo
  $PY manage.py tg_bot         # бот в этом окне; Ctrl+C — остановить всё
else
  echo "  Telegram-бот не настроен: впишите TELEGRAM_BOT_TOKEN в .env (см. КАК_ЗАПУСТИТЬ.md) и перезапустите."
  wait
fi
