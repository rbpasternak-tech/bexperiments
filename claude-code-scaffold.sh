#!/bin/bash
# claude-code-scaffold.sh
#
# USE THIS ONLY for brand-new standalone repos (NOT for new projects inside bexperiments).
# For bexperiments sub-projects, just make a folder — the root CLAUDE.md and .gitignore
# already have you covered.
#
# Usage: cd into your new repo under ~/Documents/GitHub, then run:
#   bash ~/Documents/GitHub/bexperiments/claude-code-scaffold.sh

set -e

echo "Setting up Claude Code scaffold for a standalone repo..."

# --- Create directory structure ---
mkdir -p .claude/rules
mkdir -p .claude/skills
mkdir -p .claude/agents

# --- AGENTS.md (shared agent policy) ---
if [ ! -f AGENTS.md ]; then
  cat > AGENTS.md << 'AGENTSMD'
# Project instructions

## Repository structure

- Keep the repository self-contained.
- Use descriptive folder and file names; do not retain `new-project`,
  `untitled`, or prompt fragments.
- Preserve unrelated and uncommitted changes.

## Documentation roles

- `README.md` is the human-facing project overview.
- `AGENTS.md` is the shared behavior and safety policy for coding agents.
- `CLAUDE.md` contains matching rules plus detailed commands and Claude-specific
  guidance.
- Keep `AGENTS.md` and `CLAUDE.md` behaviorally aligned.

## Safety and verification

- Never commit credentials, tokens, OAuth files, or local secret configuration.
- Test affected behavior locally before proposing a push or deployment.
- Put temporary generated material in `work/` and finished user-facing
  artifacts in `outputs/` when practical.
AGENTSMD
  echo "  Created AGENTS.md (edit this with shared project rules)"
else
  echo "  AGENTS.md already exists — skipping"
fi

# --- CLAUDE.md (starter template — edit this!) ---
if [ ! -f CLAUDE.md ]; then
  cat > CLAUDE.md << 'CLAUDEMD'
# Project Name

One-line description of what this project does.

`CLAUDE.md` and `AGENTS.md` must remain behaviorally aligned. `AGENTS.md`
contains the shared agent policy; this file adds detailed project commands and
Claude Code guidance.

## Structure

- **src/** — Main source code
- **tests/** — Test files

## Tech & Conventions

- Language: [e.g., Python 3, vanilla JS, TypeScript]
- Style: [e.g., PEP 8, 2-space indent, camelCase]
- No external build tools / Uses [webpack, vite, etc.]

## Key Commands

- **Run:** `[command to run the project]`
- **Test:** `[command to run tests]`
- **Build:** `[command to build, if applicable]`

## Credentials & Secrets

- [List any API keys, tokens, credential files and where they live]
- These should NEVER be committed to git

## Working in This Repo

- [Any rules or patterns Claude should follow when writing code here]
CLAUDEMD
  echo "  Created CLAUDE.md (edit this with your project details)"
else
  echo "  CLAUDE.md already exists — skipping"
fi

# --- .claude/settings.json (shared project settings) ---
if [ ! -f .claude/settings.json ]; then
  cat > .claude/settings.json << 'SETTINGS'
{
  "permissions": {
    "allow": []
  }
}
SETTINGS
  echo "  Created .claude/settings.json"
else
  echo "  .claude/settings.json already exists — skipping"
fi

# --- .claude/settings.local.json (local-only, gitignored) ---
if [ ! -f .claude/settings.local.json ]; then
  cat > .claude/settings.local.json << 'LOCAL'
{
  "permissions": {
    "allow": []
  }
}
LOCAL
  echo "  Created .claude/settings.local.json (local only — will be gitignored)"
else
  echo "  .claude/settings.local.json already exists — skipping"
fi

# --- .claude/rules/code-style.md (starter rule) ---
if [ ! -f .claude/rules/code-style.md ]; then
  cat > .claude/rules/code-style.md << 'RULE'
# Code Style

- [Add your language/style conventions here]
- [e.g., 2-space indent, camelCase functions, PEP 8]
- [e.g., Always write tests for new functions]
RULE
  echo "  Created .claude/rules/code-style.md (edit with your conventions)"
else
  echo "  .claude/rules/code-style.md already exists — skipping"
fi

# --- .gitignore ---
GITIGNORE_ENTRIES=(
  "# Claude Code local files"
  ".claude/settings.local.json"
  ".claude/worktrees/"
  ""
  "# OS"
  ".DS_Store"
  "Thumbs.db"
  ""
  "# Secrets"
  "*.env"
  ".env"
)

if [ -f .gitignore ]; then
  for entry in "${GITIGNORE_ENTRIES[@]}"; do
    if [ -n "$entry" ] && ! grep -qF "$entry" .gitignore 2>/dev/null; then
      echo "$entry" >> .gitignore
    fi
  done
  echo "  Updated .gitignore with Claude Code entries"
else
  printf '%s\n' "${GITIGNORE_ENTRIES[@]}" > .gitignore
  echo "  Created .gitignore"
fi

echo ""
echo "Done! Next steps:"
echo "  1. Edit AGENTS.md and CLAUDE.md with your project details"
echo "  2. Keep their shared behavior rules aligned"
echo "  3. Edit .claude/rules/code-style.md with your conventions"
echo "  4. Add any secrets/env vars to .claude/settings.local.json"
echo "  5. Commit:"
echo "     git add AGENTS.md CLAUDE.md .claude/settings.json .claude/rules/ .gitignore"
echo "     git commit -m 'Add Claude Code project scaffold'"
