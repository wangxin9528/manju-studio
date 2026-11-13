#!/usr/bin/env bash
# Optional one-shot installer for the local ComfyUI + SD1.5 art engine.
# It downloads ~2.5GB of Python dependencies and ~4.6GB of model weights.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v git >/dev/null 2>&1; then echo "需要 git" >&2; exit 1; fi
if ! command -v python3 >/dev/null 2>&1; then echo "需要 python3" >&2; exit 1; fi
if [ "$(uname -s)" != "Darwin" ] && [ "$(uname -m)" != "x86_64" ]; then
  echo "提示：本脚本按 macOS / Apple Silicon 的 PyTorch 路径编写；Linux 也可用，但请确认 MPS/CUDA 依赖。"
fi

COMFY=".tools/ComfyUI"
IPA="$COMFY/custom_nodes/ComfyUI_IPAdapter_plus"
VENV=".tools/comfyui-venv"

mkdir -p .tools
if [ ! -f "$COMFY/main.py" ]; then
  echo "→ 克隆 ComfyUI"
  git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git "$COMFY"
else
  echo "✓ ComfyUI 已存在"
fi

mkdir -p "$COMFY/custom_nodes"
if [ ! -f "$IPA/__init__.py" ]; then
  echo "→ 克隆 ComfyUI_IPAdapter_plus"
  git clone --depth 1 https://github.com/cubiq/ComfyUI_IPAdapter_plus.git "$IPA"
else
  echo "✓ ComfyUI_IPAdapter_plus 已存在"
fi

if [ ! -x "$VENV/bin/python" ]; then
  echo "→ 创建 ComfyUI Python 环境"
  python3 -m venv "$VENV"
fi
export PIP_CACHE_DIR="$PWD/.tools/pip-cache"
echo "→ 安装 PyTorch（约 150MB）"
"$VENV/bin/pip" install --upgrade pip >/dev/null
"$VENV/bin/pip" install torch torchvision torchaudio
echo "→ 安装 ComfyUI 依赖（首次较慢）"
"$VENV/bin/pip" install -r "$COMFY/requirements.txt"

echo ""
./scripts/download_models.sh

echo ""
echo "完成。启动 ComfyUI："
echo "  ./scripts/start_comfyui.sh"
echo "然后在漫构「本地设置」中选择 ComfyUI + IP-Adapter，checkpoint 选 anything-v5.safetensors。"
