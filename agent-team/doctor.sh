#!/bin/bash
# One-command diagnosis for the agent-team bot. Read-only: changes nothing.
# Prints PASS/WARN/FAIL for code version, bot processes, launchd state,
# config paths, a live health-export parse, the habit grid, and the log
# tail. Run on the Mac:
#   cd bexperiments/agent-team && ./doctor.sh
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$PROJECT_DIR")"
LOG_FILE="$REPO_DIR/.claude/telegram-state/bot.log"
LABEL="com.bexperiments.agent-team"
PYTHON="$PROJECT_DIR/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"

echo "=== agent-team doctor ==="

echo
echo "--- code ---"
echo "repo: $REPO_DIR"
echo "checkout: $(git -C "$REPO_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?') @ $(git -C "$REPO_DIR" log -1 --format='%h %s' 2>/dev/null || echo '?')"
if grep -q "MAX_TOOL_ROUNDS = 8" "$PROJECT_DIR/persona_agent.py" 2>/dev/null; then
    echo "PASS: checked-out code includes the 2026-08-01 fixes"
else
    echo "FAIL: this checkout predates the 2026-08-01 fixes — get them onto"
    echo "      this branch, then: git pull && ./install-launchd.sh"
fi

echo
echo "--- bot process ---"
BOT_PIDS=""
for pid in $(pgrep -f "python[^ ]* main\.py" 2>/dev/null || true); do
    if command -v lsof >/dev/null 2>&1; then
        cwd=$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p')
        [ "$cwd" = "$PROJECT_DIR" ] || continue
    fi
    BOT_PIDS="$BOT_PIDS $pid"
done
# shellcheck disable=SC2086
set -- $BOT_PIDS
if [ "$#" -eq 0 ]; then
    echo "FAIL: no bot process is running from $PROJECT_DIR."
    echo "      Start it: ./install-launchd.sh"
elif [ "$#" -eq 1 ]; then
    echo "PASS: exactly one bot process (pid$BOT_PIDS)"
else
    echo "FAIL: $# processes are polling the bot ($BOT_PIDS). Telegram allows"
    echo "      only one; the extras cause 409 Conflict and a silent bot."
    echo "      Fix: ./install-launchd.sh (stops strays, restarts the job)"
fi
if command -v launchctl >/dev/null 2>&1; then
    if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
        echo "PASS: launchd job $LABEL is loaded"
    else
        echo "WARN: launchd job not loaded — the bot dies with the Terminal"
        echo "      window. Install it: ./install-launchd.sh"
    fi
fi

echo
echo "--- config and data (checked with the bot's own code) ---"
"$PYTHON" - "$PROJECT_DIR" <<'PYEOF'
"""Doctor checks that import the bot's own modules against its config."""
import datetime
import json
import sys
from pathlib import Path

project = Path(sys.argv[1])
sys.path.insert(0, str(project))
import yaml
from health_export import read_health_metrics
from vault import HABITS_DIR, Vault

cfg_path = project / "config.yaml"
if not cfg_path.is_file():
    print("FAIL: config.yaml missing — copy config.example.yaml and fill it in")
    sys.exit(0)
cfg = yaml.safe_load(cfg_path.read_text()) or {}

if cfg.get("allowed_chat_ids"):
    print(f"PASS: allowed_chat_ids has {len(cfg['allowed_chat_ids'])} entry/ies")
else:
    print("FAIL: allowed_chat_ids is empty — the bot refuses every chat and "
          "scheduled duties never send")

vault = Vault(cfg.get("vault_path"))
error = vault.availability_error()
if error:
    print(f"FAIL: vault: {error}")
else:
    print(f"PASS: vault reachable at {vault.root}")
    today = datetime.date.today()
    month_rel = f"{HABITS_DIR}/{today:%Y-%m}.md"
    if (vault.root / month_rel).is_file():
        print(f"PASS: habit grid exists: {month_rel}")
    else:
        print(f"WARN: {month_rel} missing — the fixed bot creates it on the "
              "first habit write of the month")

today = datetime.date.today()
any_data = False
for label, day in (("today", today),
                   ("yesterday", today - datetime.timedelta(days=1))):
    result = read_health_metrics(cfg.get("health_export_dir"), day.isoformat())
    ok = "error" not in result
    any_data = any_data or ok
    status = "PASS" if ok else ("WARN" if any_data else "FAIL")
    print(f"{status}: health export, {label} ({day}): "
          f"{json.dumps(result, ensure_ascii=False)}")
if not any_data:
    print("      ^ neither day parsed — the error text above says why "
          "(folder, permissions, iCloud download, or the automation "
          "hasn't exported yet)")
PYEOF

echo
echo "--- last 15 lines of bot.log ---"
tail -n 15 "$LOG_FILE" 2>/dev/null || echo "(no log yet at $LOG_FILE)"
echo
echo "Done. Fix the FAIL lines top to bottom; after any change run ./install-launchd.sh"
