#!/usr/bin/env bash
# Download the SD1.5 + IP-Adapter files used by MANJU's ComfyUI art engine.
# Model weights are NOT covered by this repository's MIT license.
set -euo pipefail
cd "$(dirname "$0")/.."

MODELS_DIR="${MODELS_DIR:-$PWD/.tools/ComfyUI/models}"
CHECK_ONLY=0
FORCE=0
for arg in "$@"; do
  case "$arg" in
    --check) CHECK_ONLY=1 ;;
    --force) FORCE=1 ;;
    -h|--help)
      echo "用法: ./scripts/download_models.sh [--check] [--force]"
      echo "环境变量 MODELS_DIR 可指定 ComfyUI models 目录"
      exit 0 ;;
    *) echo "未知参数: $arg" >&2; exit 2 ;;
  esac
done

CKPT="$MODELS_DIR/checkpoints/anything-v5.safetensors"
IPADAPTER="$MODELS_DIR/ipadapter/ip-adapter-plus_sd15.safetensors"
CLIP="$MODELS_DIR/clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"

CKPT_URL="https://huggingface.co/Yntec/AnythingV5/resolve/main/AnythingV5.safetensors"
IPADAPTER_URL="https://huggingface.co/h94/IP-Adapter/resolve/main/models/ip-adapter-plus_sd15.safetensors"
CLIP_URL="https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors"

CKPT_MIN=2000000000       # ~2.1GB
IPADAPTER_MIN=90000000    # ~94MB
CLIP_MIN=2400000000       # ~2.4GB

size_of() { [ -f "$1" ] && wc -c < "$1" | tr -d ' ' || echo 0; }

download() {
  local file="$1" url="$2" min="$3" label="$4"
  local current
  current=$(size_of "$file")
  if [ "$current" -ge "$min" ] && [ "$FORCE" -eq 0 ]; then
    printf '✓ %-38s %s MB\n' "$label" "$((current / 1024 / 1024))"
    return 0
  fi
  if [ "$CHECK_ONLY" -eq 1 ]; then
    printf '✗ %-38s 缺失或不完整（%s MB）\n' "$label" "$((current / 1024 / 1024))"
    return 1
  fi
  mkdir -p "$(dirname "$file")"
  rm -f "$file.part" 2>/dev/null || true
  printf '\n→ 下载 %s\n  %s\n' "$label" "$url"
  curl -fL --retry 3 --retry-delay 3 --connect-timeout 20 \
    --progress-bar -o "$file.part" "$url"
  local got
  got=$(size_of "$file.part")
  if [ "$got" -lt "$min" ]; then
    echo "下载不完整：$got bytes，最低要求 $min" >&2
    exit 1
  fi
  mv "$file.part" "$file"
  printf '✓ %-38s %s MB\n' "$label" "$((got / 1024 / 1024))"
}

echo "模型目录: $MODELS_DIR"
echo "注意：模型权重有各自的许可证；本仓库 MIT 只覆盖代码。"
echo ""

missing=0
download "$CKPT" "$CKPT_URL" "$CKPT_MIN" "AnythingV5 (SD1.5)" || missing=1
download "$IPADAPTER" "$IPADAPTER_URL" "$IPADAPTER_MIN" "IP-Adapter Plus SD15" || missing=1
download "$CLIP" "$CLIP_URL" "$CLIP_MIN" "CLIP-ViT-H image encoder" || missing=1

if [ "$CHECK_ONLY" -eq 1 ]; then
  [ "$missing" -eq 0 ] && echo -e "\n全部模型已就绪。" || { echo -e "\n模型未齐全，运行 ./scripts/download_models.sh"; exit 1; }
else
  echo -e "\n全部模型已就绪。启动 ComfyUI：./scripts/start_comfyui.sh"
fi
