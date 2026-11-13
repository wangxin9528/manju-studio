#!/usr/bin/env bash
# Start the workspace-local ComfyUI server used by MANJU's AI art engine.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x ".tools/comfyui-venv/bin/python" ] || [ ! -f ".tools/ComfyUI/main.py" ]; then
  echo "ComfyUI 还没安装。请先运行安装脚本（见 README 5.3）。"
  exit 1
fi
if curl -fsS "http://127.0.0.1:${PORT:-8188}/system_stats" >/dev/null 2>&1; then
  echo "ComfyUI 已经在运行：http://127.0.0.1:${PORT:-8188}"
  exit 0
fi
cd .tools/ComfyUI
export PYTORCH_ENABLE_MPS_FALLBACK=1
exec ../comfyui-venv/bin/python main.py --listen 127.0.0.1 --port "${PORT:-8188}" "$@"
