#!/usr/bin/env bash
# Приложение на своём телефоне через Expo Go — без Android Studio и без сборки.
#   1) в первом окне: bash scripts/run_local.sh   (сайт + https-адрес; адрес попадёт в mobile/.env.local)
#   2) во втором окне: bash scripts/run_app.sh
#   3) на телефоне: приложение «Expo Go» (Play Market / App Store) → сканировать QR-код из этого окна.
set -euo pipefail
cd "$(dirname "$0")/../mobile"
export PATH="$HOME/.local/node/bin:$PATH"
command -v node >/dev/null || { echo "Нет Node.js — сначала: bash scripts/app_setup.sh"; exit 1; }
[ -d node_modules ] || npm install
if [ -f .env.local ]; then
  echo "Сервер для приложения: $(cut -d= -f2- .env.local)"
else
  echo "Сервер для приложения: https://ilm4.com (mobile/.env.local нет — запустите scripts/run_local.sh, чтобы тестировать свой ПК)"
fi
# --tunnel: телефон подключается через интернет, не нужно быть в одной Wi-Fi-сети с ПК
npx expo start --tunnel
