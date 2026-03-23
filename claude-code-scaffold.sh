#!/bin/bash
# claude-code-scaffold.sh
#
# USE THIS ONLY for brand-new standalone repos (NOT for new projects inside bexperiments).
# For bexperiments sub-projects, just make a folder — the root CLAUDE.md and .gitignore
# already have you covered.
#
# Usage: cd into your new repo, then run:
#   bash ~/bexperiments/claude-code-scaffold.sh

set -e

echo "Setting up Claude Code scaffold for a standalone repo..."

# --- Create directory structure ---
mkdir -p .claude/rules
mkdir -p .claude/skills
mkdir -p .claude/agents

# --- CLAUDE.md (starter template — edit this!) ---
if [ ! -f CLAUDE.md ]; then
  cat > CLAUDE.md << 'CLAUDEMD'
# Project Name

One-line description of what this project does.

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
echo "  1. Edit CLAUDE.md with your project details"
echo "  2. Edit .claude/rules/code-style.md with your conventions"
echo "  3. Add any secrets/env vars to .claude/settings.local.json"
echo "  4. Commit:"
echo "     git add CLAUDE.md .claude/settings.json .claude/rules/ .gitignore"
echo "     git commit -m 'Add Claude Code project scaffold'"
