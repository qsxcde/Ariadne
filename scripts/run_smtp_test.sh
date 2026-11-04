#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose -f docker-compose.test.yml up -d mailhog
trap 'docker compose -f docker-compose.test.yml down' EXIT

for _ in $(seq 1 20); do
  if curl -fsS http://127.0.0.1:8025/api/v2/messages >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

export ARIADNE_SMTP_DOCKER=1
uv run --project backend pytest -m smtp_docker "$@"
