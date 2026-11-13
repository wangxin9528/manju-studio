#!/usr/bin/env bash
# Install optional local Git hooks for this repository.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .git/hooks
cp scripts/git-hooks/post-commit .git/hooks/post-commit
chmod +x .git/hooks/post-commit
echo "已安装 post-commit：提交到 main 后自动 push origin main"
echo "日志：.git/auto-push.log"
