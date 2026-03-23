# New Project Setup Checklist for Claude Code

Use this every time you start a new project in Claude Code to get the scaffolding right from the start.

---

## 1. Initialize the repo

- [ ] `git init` (if not cloned from an existing repo)
- [ ] Create your first file or `README.md` so you have something to commit

## 2. Create the Claude Code scaffold

Run the setup script (`claude-code-scaffold.sh` — see companion file), **or** do it manually:

- [ ] Create `CLAUDE.md` at the project root
- [ ] Create `.claude/settings.json` (shared team/project settings)
- [ ] Create `.claude/settings.local.json` (your local-only settings — secrets, env vars)
- [ ] Create `.claude/rules/` directory with at least one rule file
- [ ] Optionally create `.claude/skills/` and `.claude/agents/` directories

## 3. Write your CLAUDE.md

Keep it under 200 lines. Include:

- [ ] One-line project description
- [ ] List of sub-projects or key directories with entry points
- [ ] Tech stack and language conventions (indent style, naming, etc.)
- [ ] Key commands (build, test, run, serve)
- [ ] Credentials/secrets and where they live (so Claude knows what NOT to commit)
- [ ] Deployment notes (how and where it ships)
- [ ] Any "rules of the road" for working in the codebase

**Tip:** Run `claude /init` in your project first to auto-generate a draft, then trim it down.

## 4. Set up .gitignore BEFORE your first commit

- [ ] Add `.claude/settings.local.json` (contains secrets)
- [ ] Add `.claude/worktrees/` (Claude Code temp files)
- [ ] Add OS files (`.DS_Store`, `Thumbs.db`)
- [ ] Add language-specific ignores (`__pycache__/`, `node_modules/`, `venv/`)
- [ ] Add credential files (`*.env`, `credentials.json`, `token.json`)

## 5. Git commit structure

- [ ] Commit these files to git (so they persist and sync):
  - `CLAUDE.md`
  - `.claude/settings.json`
  - `.claude/rules/*.md`
  - `.claude/skills/` (if any)
  - `.claude/agents/` (if any)
  - `.gitignore`

- [ ] Do NOT commit (should be in `.gitignore`):
  - `.claude/settings.local.json`
  - `.claude/worktrees/`
  - Any plugin state directories
  - Credentials, tokens, `.env` files

## 6. First commit

```bash
git add CLAUDE.md .claude/settings.json .claude/rules/ .gitignore
git commit -m "Add Claude Code project scaffold"
```

## 7. Verify

- [ ] Run `git status` — no secrets or local-only files should appear as tracked
- [ ] Open Claude Code in the project — it should pick up your CLAUDE.md automatically
- [ ] Try asking Claude about your project — it should know the structure and conventions

---

## Quick Reference: What Goes Where

| File | Purpose | Commit to git? |
|------|---------|----------------|
| `CLAUDE.md` | Project instructions Claude reads every session | Yes |
| `.claude/settings.json` | Shared permissions and config | Yes |
| `.claude/settings.local.json` | Your secrets, env vars, local prefs | **No** |
| `.claude/rules/*.md` | Topic-specific instructions | Yes |
| `.claude/skills/*/SKILL.md` | On-demand workflows | Yes |
| `.claude/agents/*.md` | Custom subagents | Yes |
| `.gitignore` | Protects secrets from accidental commits | Yes |
