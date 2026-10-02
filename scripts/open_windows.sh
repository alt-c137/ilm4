#!/usr/bin/env bash
# Открыть ДВА обычных окна Ubuntu на рабочем столе Windows: сайт (+бот) и приложение (Expo).
# Закрыть любое — Ctrl+C в нём или крестик окна.
#
#   bash scripts/open_windows.sh          # адрес Cloudflare
#   bash scripts/open_windows.sh ngrok    # через ngrok
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="${1:-}"
command -v powershell.exe >/dev/null || { echo "Это работает только в Ubuntu под Windows (WSL). Запустите вручную: bash scripts/run_local.sh и bash scripts/run_app.sh"; exit 1; }
DISTRO="${WSL_DISTRO_NAME:-Ubuntu}"
win() {   # win <команда…> — новое окно Ubuntu с этой командой
  local args="'-d','$DISTRO','--','bash','-l','$ROOT/scripts/_window.sh'"
  for a in "$@"; do args="$args,'$a'"; done
  (cd /mnt/c && powershell.exe -NoProfile -Command "Start-Process -FilePath wsl.exe -ArgumentList $args" </dev/null >/dev/null 2>&1) || true
}
before=$(stat -c %Y "$ROOT/mobile/.env.local" 2>/dev/null || echo 0)
if [ -n "$MODE" ]; then win bash "$ROOT/scripts/run_local.sh" "$MODE"; else win bash "$ROOT/scripts/run_local.sh"; fi
echo "Окно сайта открыто. Жду адрес сайта…"
for _ in $(seq 1 90); do
  now=$(stat -c %Y "$ROOT/mobile/.env.local" 2>/dev/null || echo 0)
  [ "$now" != "$before" ] && break
  sleep 1
done
echo "Сайт: $(cut -d= -f2- "$ROOT/mobile/.env.local" 2>/dev/null || echo '— адрес не появился, смотрите окно сайта')"
win bash "$ROOT/scripts/run_app.sh"
echo "Окно приложения открыто: в нём появится QR-код для Expo Go."
