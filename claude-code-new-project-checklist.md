# Starting a New Project in bexperiments

Code projects live in descriptive subfolders inside `bexperiments`, which is
one git repository. A branch or pull request is not a separate Finder project.

---

## Steps

### 1. Open Terminal and go to bexperiments

```bash
cd ~/Documents/GitHub/bexperiments
```

### 2. Make a folder for your new project

```bash
mkdir contract-review-playground
cd contract-review-playground
```

Replace `contract-review-playground` with a short, descriptive name for the
actual outcome. Never keep `new-project`, `untitled`, or a prompt fragment as
the final folder name.

### 3. Start building

That's it for setup. You don't need to run `git init` — bexperiments already has git. You don't need a new `.gitignore` — the one at the root already covers you. You don't need a new `CLAUDE.md` — the one at the root tells Claude about the whole repo.

Just start creating files. Open Claude Code from inside bexperiments and tell it what you want to build.

### 4. Update the repository catalog and inventory

Once the project is retained, add it to the human catalog in `README.md` and
the matching detailed inventory in `CLAUDE.md`. Keep the same display name and
alphabetical order in both files. For example:

```
- **Contract Review Playground** — `contract-review-playground/`: short description. Entry: `contract-review-playground/index.html`.
```

### 5. Commit your work

```bash
cd ~/Documents/GitHub/bexperiments
git add contract-review-playground/ README.md CLAUDE.md
git commit -m "Add contract review playground"
git push
```

---

## What's already set up (you don't need to redo these)

These files live at the root of bexperiments and cover all projects:

| File | What it does |
|------|-------------|
| `README.md` | Human-facing project catalog and links |
| `AGENTS.md` | Shared behavior and safety policy for coding agents |
| `CLAUDE.md` | Detailed project inventory, commands, and Claude Code guidance |
| `.claude/settings.json` | Shared permissions (e.g., pre-approved commands) |
| `.claude/settings.local.json` | Your secrets — Telegram token, etc. (gitignored) |
| `.claude/rules/code-style.md` | Code style conventions Claude follows |
| `.gitignore` | Keeps secrets, `.DS_Store`, `__pycache__`, etc. out of git |

---

## When would I need the scaffold script?

Only if you start a brand-new, separate repo that is NOT inside bexperiments. For example, if you start a work project or something you want in its own GitHub repo. Then you'd do:

```bash
mkdir ~/Documents/GitHub/totally-separate-project
cd ~/Documents/GitHub/totally-separate-project
git init
bash ~/Documents/GitHub/bexperiments/claude-code-scaffold.sh
```

That creates all the Claude Code files from scratch since there's no parent repo providing them.
