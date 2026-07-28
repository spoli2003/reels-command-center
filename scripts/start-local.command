#!/bin/zsh
set -e
cd "$(dirname "$0")/.."
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Utworzono .env. Przed pierwszym połączeniem Google ustaw własne SESSION_SECRET i TOKEN_ENCRYPTION_KEY."
fi
open -a Docker || true
docker compose up --build
