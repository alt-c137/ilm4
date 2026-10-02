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
# iPhone: Expo Go открывает проект, только если ПК и телефон вошли в один аккаунт Expo (Android — без этого).
if ! npx expo whoami >/dev/null 2>&1; then
  echo
  echo "Вы не вошли в аккаунт Expo. Для Android это не обязательно, для iPhone — обязательно."
  echo "Аккаунт бесплатный: https://expo.dev/signup . В Expo Go на iPhone войдите тем же логином."
  read -r -p "Войти сейчас? [y/N] " ans || ans=n
  case "$ans" in y|Y|д|Д) npx expo login || true ;; esac
else
  echo "Аккаунт Expo: $(npx expo whoami 2>/dev/null) — на iPhone в Expo Go войдите тем же логином."
fi
# --tunnel: телефон подключается через интернет, не нужно быть в одной Wi-Fi-сети с ПК
npx expo start --tunnel
