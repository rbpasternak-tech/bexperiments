#!/usr/bin/env bash
# Launch a tmux session for the bexperiments monorepo, one window per project,
# with a Claude Code session ready in each project window.
# Usage: ./tmux-bexperiments.sh                    (run from anywhere)
#        ./tmux-bexperiments.sh my-new-project     (also add windows for these folders)
#        NO_CLAUDE=1 ./tmux-bexperiments.sh        (skip auto-launching claude)
# Safe to rerun: it adds any missing project windows to the existing session
# instead of just reattaching, so new projects get picked up.
# Detach with prefix(Ctrl-b) d; reattach with: tmux attach -t bexperiments

set -euo pipefail

SESSION="bexperiments"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PROJECTS=(doc-find-replace legal-doc-catalog clause-remediation-app
          trends-dashboard newsletter-digest dynamic-workflows-cookbook)
# Extra project folders passed as arguments get windows too.
PROJECTS+=("$@")

FRESH=""
if ! tmux has-session -t "$SESSION" 2>/dev/null; then
  FRESH=1
  # First window: a split for the repo root + a local web server pane.
  tmux new-session -d -s "$SESSION" -n repo -c "$ROOT"
  tmux split-window -h -t "$SESSION:repo" -c "$ROOT"
  tmux send-keys -t "$SESSION:repo.2" 'echo "serve with: python -m http.server 8000"' C-m
  tmux select-pane -t "$SESSION:repo.1"
fi

# One window per project, each starting in its folder. Unless NO_CLAUDE is
# set, launch a Claude Code session in each new window so every tab is a
# ready-to-go agent. Existing windows sitting at a bare shell prompt get
# claude started too; windows already running something are left alone.
existing="$(tmux list-windows -t "$SESSION" -F '#{window_name}')"

# Watchtower: a dashboard window showing Claude sessions, subagents, and
# loops across all projects (reads transcript activity from ~/.claude).
if ! grep -qx watchtower <<<"$existing"; then
  tmux new-window -d -t "$SESSION" -n watchtower -c "$ROOT"
  tmux send-keys -t "$SESSION:watchtower" "python3 '$ROOT/watchtower.py'" C-m
else
  running="$(tmux display -p -t "$SESSION:watchtower.1" '#{pane_current_command}')"
  case "$running" in
    zsh|bash|sh) tmux send-keys -t "$SESSION:watchtower.1" "python3 '$ROOT/watchtower.py'" C-m ;;
  esac
fi

for proj in "${PROJECTS[@]}"; do
  [ -d "$ROOT/$proj" ] || continue
  if grep -qx "$proj" <<<"$existing"; then
    [ -n "${NO_CLAUDE:-}" ] && continue
    running="$(tmux display -p -t "$SESSION:$proj.1" '#{pane_current_command}')"
    case "$running" in
      zsh|bash|sh) tmux send-keys -t "$SESSION:$proj.1" 'claude' C-m ;;
    esac
    continue
  fi
  tmux new-window -d -t "$SESSION" -n "$proj" -c "$ROOT/$proj"
  [ -n "${NO_CLAUDE:-}" ] || tmux send-keys -t "$SESSION:$proj" 'claude' C-m
done

[ -n "$FRESH" ] && tmux select-window -t "$SESSION:repo"

# Attaching inside tmux fails ("sessions should be nested with care"), so
# switch the current client instead when already in a tmux session.
if [ -n "${TMUX:-}" ]; then
  exec tmux switch-client -t "$SESSION"
else
  exec tmux attach -t "$SESSION"
fi
