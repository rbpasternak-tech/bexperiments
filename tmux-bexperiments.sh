#!/usr/bin/env bash
# Launch a tmux session for the bexperiments monorepo, one window per project.
# Usage: ./tmux-bexperiments.sh   (run from anywhere)
# Detach with prefix(Ctrl-b) d; reattach with: tmux attach -t bexperiments

set -euo pipefail

SESSION="bexperiments"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# If the session already exists, just attach to it.
if tmux has-session -t "$SESSION" 2>/dev/null; then
  exec tmux attach -t "$SESSION"
fi

# First window: a split for the repo root + a local web server pane.
tmux new-session -d -s "$SESSION" -n repo -c "$ROOT"
tmux split-window -h -t "$SESSION:repo" -c "$ROOT"
tmux send-keys -t "$SESSION:repo.2" 'echo "serve with: python -m http.server 8000"' C-m
tmux select-pane -t "$SESSION:repo.1"

# One window per project, each starting in its folder.
for proj in doc-find-replace legal-doc-catalog clause-remediation-app \
            trends-dashboard newsletter-digest dynamic-workflows-cookbook; do
  [ -d "$ROOT/$proj" ] && tmux new-window -t "$SESSION" -n "$proj" -c "$ROOT/$proj"
done

tmux select-window -t "$SESSION:repo"
exec tmux attach -t "$SESSION"
