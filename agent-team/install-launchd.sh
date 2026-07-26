#!/bin/bash
# Installs the agent-team Telegram bot as a macOS launchd user agent, so it
# starts at login, restarts on crash, and runs without a Terminal window.
# Re-run any time; it replaces the existing job. Uninstall with:
#   launchctl bootout "gui/$(id -u)/com.bexperiments.agent-team"
#   rm ~/Library/LaunchAgents/com.bexperiments.agent-team.plist
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.bexperiments.agent-team"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$(dirname "$PROJECT_DIR")/.claude/telegram-state"
LOG_FILE="$LOG_DIR/bot.log"

PYTHON="$PROJECT_DIR/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
    PYTHON="$(command -v python3)"
    echo "Note: no .venv found, using $PYTHON"
fi

if [ ! -f "$PROJECT_DIR/config.yaml" ]; then
    echo "ERROR: $PROJECT_DIR/config.yaml not found. Set it up first." >&2
    exit 1
fi

mkdir -p "$LOG_DIR" "$HOME/Library/LaunchAgents"

# Only one process may poll the bot token: stop a previous launchd job and
# best-effort kill a manually started main.py.
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
pkill -f "[.]venv/bin/python main.py" 2>/dev/null || true
sleep 1

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG_FILE</string>
    <key>StandardErrorPath</key>
    <string>$LOG_FILE</string>
</dict>
</plist>
PLIST

launchctl bootstrap "gui/$(id -u)" "$PLIST"
sleep 2
echo "--- launchd status ---"
launchctl print "gui/$(id -u)/$LABEL" | grep -E "state|pid|last exit" || true
echo "--- last log lines ($LOG_FILE) ---"
tail -n 5 "$LOG_FILE" 2>/dev/null || echo "(no log output yet)"
echo
echo "Installed. The bot now starts at login and restarts on crash."
