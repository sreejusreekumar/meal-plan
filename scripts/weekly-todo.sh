#!/bin/zsh
# Saturday morning on the Mac: fetch what the GitHub Action published, push next week's list to
# Microsoft To Do. Installed by scripts/install-launchd.sh; logs to ~/Library/Logs/meal-plan.log.
set -euo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
cd "$(dirname "$0")/.."
echo "== $(date '+%Y-%m-%d %H:%M') weekly-todo"
git pull --ff-only
if ! uv run mealplan todo push --week next; then
  echo "To Do push failed. If it says not signed in, run: uv run mealplan todo login"
  exit 1
fi
