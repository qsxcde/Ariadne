#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose -f docker-compose.test.yml up -d --build
trap 'docker compose -f docker-compose.test.yml down -v' EXIT

for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:18080/health >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

export SCIPAL_MOCK_LLM=1
export DEEPSEEK_BASE_URL=http://127.0.0.1:18080/v1
export DEEPSEEK_API_KEY=mock
export DEEPSEEK_MODEL=mock-model
export LLM_FALLBACK_ENABLED=false
export EMBEDDING_REMOTE_API_KEY=mock
export EMBEDDING_REMOTE_BASE_URL=http://127.0.0.1:18080/v1
export EMBEDDING_REMOTE_MODEL=mock-embed
export EMBEDDING_DIM=8

uv run --project backend pytest -m mock_llm "$@"
