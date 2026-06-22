#!/usr/bin/env bash
# Start the full stack in the foreground with logs.
set -euo pipefail
cd "$(dirname "$0")/.."
test -f .env || cp .env.example .env
docker compose up --build
