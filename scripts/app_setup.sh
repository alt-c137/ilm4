#!/usr/bin/env bash
# Один раз: Node.js (без sudo, в ~/.local/node) и модули мобильного приложения.
#   bash scripts/app_setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."
NODE_DIR="$HOME/.local/node"
if [ ! -x "$NODE_DIR/bin/node" ]; then
  echo "Скачиваю Node.js 22 (один раз)…"
  mkdir -p "$NODE_DIR"
  curl -fsSL https://nodejs.org/dist/v22.20.0/node-v22.20.0-linux-x64.tar.xz | tar -xJ -C "$NODE_DIR" --strip-components=1
fi
export PATH="$NODE_DIR/bin:$PATH"
grep -q '.local/node/bin' "$HOME/.bashrc" 2>/dev/null || echo 'export PATH="$HOME/.local/node/bin:$PATH"' >> "$HOME/.bashrc"
cd mobile
npm install
echo
echo "Готово. Запуск на телефоне: bash scripts/run_app.sh"
