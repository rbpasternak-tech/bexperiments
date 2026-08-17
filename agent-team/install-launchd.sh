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
# Log lives OUTSIDE the repo. The repo is in iCloud-synced ~/Documents, and
# iCloud's "Optimize Mac Storage" evicts idle files to dataless placeholders
# that launchd cannot rematerialize when it opens StandardOutPath at spawn —
# which failed with EX_CONFIG (78) and crash-looped the bot. ~/Library/Logs is
# not iCloud-synced, so the log file stays local and openable.
LOG_DIR="$HOME/Library/Logs/agent-team"
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
# kill any main.py whose working directory is this project (catches manual
# runs with any python, without touching other projects' main.py).
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
for pid in $(pgrep -f "python[^ ]* main\.py" 2>/dev/null || true); do
    cwd=$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p')
    if [ "$cwd" = "$PROJECT_DIR" ]; then
        kill "$pid" 2>/dev/null || true
    fi
done
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
    <!-- Unbuffered so a startup crash lands in the log instead of dying in
         Python's stdout buffer (block-buffered when stdout is a file). -->
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONUNBUFFERED</key>
        <string>1</string>
    </dict>
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
