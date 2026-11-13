#!/usr/bin/env bash
# Optional: install a workspace-local Ollama runtime and the 3B story model.
# It does not need Homebrew or admin rights, and keeps models under .tools/.
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p .tools .tools/home .tools/ollama-models data
if [ ! -x ".tools/ollama" ]; then
  echo "→ 下载 Ollama（约 186MB）"
  curl -fL --retry 3 -o /tmp/ollama-darwin.tgz \
    "https://github.com/ollama/ollama/releases/download/v0.40.16/ollama-darwin.tgz"
  tar -xzf /tmp/ollama-darwin.tgz -C .tools
  chmod +x .tools/ollama
fi

if ! curl -fsS "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
  echo "→ 启动本地 Ollama"
  HOME="$PWD/.tools/home" OLLAMA_MODELS="$PWD/.tools/ollama-models" \
    nohup .tools/ollama serve > data/ollama.log 2>&1 &
  sleep 3
fi

echo "→ 拉取 qwen2.5:3b（约 2GB，只需一次）"
HOME="$PWD/.tools/home" OLLAMA_MODELS="$PWD/.tools/ollama-models" \
  .tools/ollama pull qwen2.5:3b

echo "完成。打开漫构 → 设置 → 启用 LLM，Base URL 填 http://127.0.0.1:11434/v1，模型填 qwen2.5:3b。"
