#!/usr/bin/env bash
# 在 GeneAgent 根目录执行：bash scripts/github_publish.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v gh >/dev/null 2>&1; then
  echo "请先安装 GitHub CLI: https://cli.github.com/"
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "请先登录: gh auth login"
  exit 1
fi

gh repo create GeneAgent --public \
  --description "East Asia WWII multi-agent strategic sim (东亚风云)" \
  --source=. --remote=origin --push

echo "完成。仓库地址:"
gh repo view --web 2>/dev/null || gh repo view --json url -q .url
