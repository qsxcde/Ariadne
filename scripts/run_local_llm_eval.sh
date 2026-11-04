#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

MODEL_DIR="${ARIADNE_MODEL_DIR:-docker/models}"
mkdir -p "$MODEL_DIR"

download() {
  local url="$1" target="$2"
  if [ ! -f "$target" ]; then
    echo "Downloading $target ..."
    curl -L --fail --retry 3 -o "$target" "$url"
  fi
}

download \
  "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf" \
  "$MODEL_DIR/qwen2.5-3b.gguf"
download \
  "https://huggingface.co/nomic-ai/nomic-embed-text-v1.5-GGUF/resolve/main/nomic-embed-text-v1.5.Q4_K_M.gguf" \
  "$MODEL_DIR/nomic-embed.gguf"

docker compose -f docker-compose.local-llm.yml up -d
trap 'docker compose -f docker-compose.local-llm.yml down' EXIT
sleep 5

docker exec ariadne-ollama sh -c 'printf "FROM /models/qwen2.5-3b.gguf\n" > /tmp/Modelfile.qwen && ollama create qwen3 -f /tmp/Modelfile.qwen'
docker exec ariadne-ollama sh -c 'printf "FROM /models/nomic-embed.gguf\n" > /tmp/Modelfile.embed && ollama create nomic-embed -f /tmp/Modelfile.embed'

export ARIADNE_LOCAL_LLM=1
export DEEPSEEK_BASE_URL=http://127.0.0.1:11434/v1
export DEEPSEEK_API_KEY=ollama
export DEEPSEEK_MODEL=qwen3
export LLM_FALLBACK_ENABLED=false
export EMBEDDING_REMOTE_API_KEY=ollama
export EMBEDDING_REMOTE_BASE_URL=http://127.0.0.1:11434/v1
export EMBEDDING_REMOTE_MODEL=nomic-embed
export EMBEDDING_DIM=768

uv run --project backend pytest -m local_llm "$@"
