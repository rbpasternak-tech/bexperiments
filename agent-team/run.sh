#!/bin/bash
# launchd entry point for the agent-team bot.
#
# Why this wrapper exists: the repo lives in iCloud-synced ~/Documents with
# "Optimize Mac Storage" on, which evicts idle files (source .py, config.yaml)
# to dataless placeholders. A launchd-spawned process cannot transparently
# fault a dataless file back in — read() dies with
# OSError(11, 'Resource deadlock avoided') — so the bot crash-looped and the
# nightly health->Obsidian push silently stopped. `brctl download` DOES work
# under launchd, so we materialize the project dir here, before Python opens
# config.yaml. The interpreter itself lives OUTSIDE iCloud (see below) so it is
# never evicted. Health-export/vault files are materialized separately by
# health_export.py at read time.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PY="$HOME/Library/Application Support/agent-team/.venv/bin/python"

cd "$PROJECT_DIR"

# Pull the source + config back to disk if iCloud evicted them, and wait until
# config.yaml is a real (non-dataless) file before launching.
brctl download "$PROJECT_DIR" >/dev/null 2>&1 || true
for _ in $(seq 1 60); do
    case "$(stat -f '%Sf' "$PROJECT_DIR/config.yaml" 2>/dev/null)" in
        *dataless*) brctl download "$PROJECT_DIR/config.yaml" >/dev/null 2>&1 || true; sleep 1 ;;
        *) break ;;
    esac
done

exec "$VENV_PY" main.py
