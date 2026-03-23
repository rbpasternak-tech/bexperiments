# Starting a New Project in bexperiments

Your projects all live as subfolders inside bexperiments, which is one git repo. Here's what to do every time you start something new.

---

## Steps

### 1. Open Terminal and go to bexperiments

```bash
cd ~/bexperiments
```

### 2. Make a folder for your new project

```bash
mkdir my-new-project
cd my-new-project
```

(Replace "my-new-project" with whatever you're building.)

### 3. Start building

That's it for setup. You don't need to run `git init` — bexperiments already has git. You don't need a new `.gitignore` — the one at the root already covers you. You don't need a new `CLAUDE.md` — the one at the root tells Claude about the whole repo.

Just start creating files. Open Claude Code from inside bexperiments and tell it what you want to build.

### 4. Update the root CLAUDE.md

Once your project has taken shape, add a one-liner to the "Current Projects" section in `~/bexperiments/CLAUDE.md` so Claude knows it exists. For example:

```
- **my-new-project/** — Short description of what it does. Entry: `my-new-project/index.html`
```

### 5. Commit your work

```bash
cd ~/bexperiments
git add my-new-project/ CLAUDE.md
git commit -m "Add my-new-project"
git push
```

---

## What's already set up (you don't need to redo these)

These files live at the root of bexperiments and cover all projects:

| File | What it does |
|------|-------------|
| `CLAUDE.md` | Tells Claude about the repo, conventions, and all projects |
| `.claude/settings.json` | Shared permissions (e.g., pre-approved commands) |
| `.claude/settings.local.json` | Your secrets — Telegram token, etc. (gitignored) |
| `.claude/rules/code-style.md` | Code style conventions Claude follows |
| `.gitignore` | Keeps secrets, `.DS_Store`, `__pycache__`, etc. out of git |

---

## When would I need the scaffold script?

Only if you start a brand-new, separate repo that is NOT inside bexperiments. For example, if you start a work project or something you want in its own GitHub repo. Then you'd do:

```bash
mkdir ~/Documents/totally-separate-project
cd ~/Documents/totally-separate-project
git init
bash ~/bexperiments/claude-code-scaffold.sh
```

That creates all the Claude Code files from scratch since there's no parent repo providing them.
