#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 1; }
command -v npm >/dev/null || { echo "npm is required to install the official gmgn-cli" >&2; exit 1; }

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e '.[dev]'
npm install --global gmgn-cli

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env; fill in TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID and GMGN_API_KEY."
fi

mkdir -p data
echo "Bootstrap complete. Run: .venv/bin/essentials"

