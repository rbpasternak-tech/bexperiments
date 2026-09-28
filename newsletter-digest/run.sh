#!/bin/bash
# launchd entry point for the newsletter digest (manual-run copy).
#
# Why this wrapper exists: the repo lives in iCloud-synced ~/Documents with
# "Optimize Mac Storage" on, which evicts idle files (source .py, config.yaml,
# credentials.json, token.json) to dataless placeholders. A launchd-spawned
# process cannot transparently fault a dataless file back in — read() dies
# with OSError(11, 'Resource deadlock avoided') — which is how the digest
# silently stopped in September 2026. `brctl download` DOES work under
# launchd, so we materialize the project dir here before Python opens
# anything. The interpreter lives OUTSIDE iCloud (~/Library) so it is never
# evicted, and the Anthropic key comes from the login Keychain instead of
# being written into the plist in plaintext.
#
# Keychain item (create/rotate with):
#   security add-generic-password -a "$USER" -s newsletter-digest-anthropic \
#       -l "newsletter-digest Anthropic API key" -w "<new key>" -U
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PY="$HOME/Library/Application Support/newsletter-digest/.venv/bin/python"
KEYCHAIN_SERVICE="newsletter-digest-anthropic"

cd "$PROJECT_DIR"

# Pull the source + config back to disk if iCloud evicted them, and wait until
# the files Python opens first are real (non-dataless) before launching.
brctl download "$PROJECT_DIR" >/dev/null 2>&1 || true
for f in config.yaml credentials.json token.json; do
    for _ in $(seq 1 60); do
        case "$(stat -f '%Sf' "$PROJECT_DIR/$f" 2>/dev/null)" in
            *dataless*) brctl download "$PROJECT_DIR/$f" >/dev/null 2>&1 || true; sleep 1 ;;
            *) break ;;
        esac
    done
done

ANTHROPIC_API_KEY="$(security find-generic-password -s "$KEYCHAIN_SERVICE" -w)"
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ERROR: no Keychain item for service '$KEYCHAIN_SERVICE'" >&2
    exit 78
fi
export ANTHROPIC_API_KEY

exec "$VENV_PY" main.py "$@"
