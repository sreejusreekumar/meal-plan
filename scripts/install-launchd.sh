#!/bin/zsh
# Install (or reinstall) the Saturday 06:30 launchd job that runs scripts/weekly-todo.sh.
# Remove with: launchctl bootout gui/$(id -u)/com.mealplan.todo
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
LABEL=com.mealplan.todo
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>/bin/zsh</string><string>$REPO/scripts/weekly-todo.sh</string></array>
  <key>StartCalendarInterval</key><dict><key>Weekday</key><integer>6</integer><key>Hour</key><integer>6</integer><key>Minute</key><integer>30</integer></dict>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/meal-plan.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/meal-plan.log</string>
</dict></plist>
PL
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Installed $LABEL: Saturdays 06:30, log at ~/Library/Logs/meal-plan.log"
echo "Run it now with: launchctl kickstart -k gui/$(id -u)/$LABEL"
