#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8787}"
HOST="${HOST:-127.0.0.1}"
URL="http://127.0.0.1:${PORT}"

if [ ! -x ".venv/bin/python" ]; then
  echo "→ 创建本地运行环境 .venv"
  python3 -m venv .venv
fi

if ! .venv/bin/python -c "import fastapi, uvicorn, PIL, numpy, edge_tts, imageio_ffmpeg, httpx" >/dev/null 2>&1; then
  echo "→ 安装依赖（只需一次）"
  .venv/bin/python -m pip install --upgrade pip >/dev/null
  .venv/bin/pip install -r requirements.txt
fi

mkdir -p data/projects data/cache output

# Optional workspace-local Ollama runtime (inert until a project uses LLM).
if [ -x ".tools/ollama" ] && ! curl -fsS "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
  mkdir -p .tools/home .tools/ollama-models
  echo "→ 启动本地 Ollama"
  HOME="$PWD/.tools/home" OLLAMA_MODELS="$PWD/.tools/ollama-models" \
    nohup .tools/ollama serve > data/ollama.log 2>&1 &
fi

# Optional workspace-local ComfyUI + SD model runtime.
if [ -f ".tools/ComfyUI/main.py" ] && ! curl -fsS "http://127.0.0.1:8188/system_stats" >/dev/null 2>&1; then
  echo "→ 启动本地 ComfyUI（AI 插画）"
  nohup ./scripts/start_comfyui.sh > data/comfyui.log 2>&1 &
fi

if curl -fsS "${URL}/api/health" >/dev/null 2>&1; then
  echo "漫构已经在运行：${URL}"
  if [ -z "${MANJU_NO_OPEN:-}" ] && command -v open >/dev/null 2>&1; then open "${URL}"; fi
  exit 0
fi

echo ""
echo "  漫构 MANJU STUDIO"
echo "  → ${URL}"
echo "  本地片场已启动，按 Ctrl+C 停止。"
echo ""

if [ -z "${MANJU_NO_OPEN:-}" ] && command -v open >/dev/null 2>&1; then
  ( sleep 1.8; open "${URL}" ) >/dev/null 2>&1 &
fi

exec .venv/bin/uvicorn app.main:app --host "${HOST}" --port "${PORT}"
