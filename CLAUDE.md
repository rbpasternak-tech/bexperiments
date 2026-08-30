# bexperiments

Rebecca's personal monorepo for small applications, automations, and learning
experiments. The canonical local path is
`~/Documents/GitHub/bexperiments/`; `~/bexperiments` is a compatibility
shortcut to the same repository.

`CLAUDE.md` and `AGENTS.md` must remain behaviorally aligned. `AGENTS.md` is the
canonical shared agent policy. This file adds the detailed project inventory,
commands, credentials guidance, and deployment notes used by Claude Code.

## Repository structure

- Every retained project lives in a descriptive, self-contained root-level
  folder.
- Do not create cross-project imports without explicit approval.
- Do not use generic folder names such as `my-new-project`, `new-project`, or
  `untitled`.
- When a retained project is added, removed, or renamed, update this inventory
  and the catalog in `README.md` together.
- Git branches and pull requests belong to this repository; do not create local
  folders that duplicate PRs.

## Project inventory

Projects use the same alphabetical order and display names as `README.md`.

- **Agent Team** — `agent-team/`: Telegram bot hosting Claude-powered literary
  personas. Entry: `agent-team/main.py`.
- **Clause Remediation App** — `clause-remediation-app/`: Flask prototype for
  clause review and remediation. Entry: `clause-remediation-app/server.py`.
- **Doc Find & Replace** — `doc-find-replace/`: browser-based bulk `.docx` and
  `.pdf` editor. Entry: `doc-find-replace/index.html`.
- **Dynamic Workflows Cookbook** — `dynamic-workflows-cookbook/`: coordinated
  agent patterns, run logs, clause examples, and an interactive pattern board.
  Entry: `dynamic-workflows-cookbook/README.md`.
- **Habit Tracker** — `habit-tracker/`: offline-capable vanilla JavaScript PWA.
  Entry: `habit-tracker/index.html`.
- **Legal Doc Catalog** — `legal-doc-catalog/`: Supabase-backed legal-document
  catalog and search app. Entry: `legal-doc-catalog/index.html`.
- **Loop & Graph Workflows** — `loop-graph-workflows/`: verifier-controlled goal
  loop and dependency-graph workflow experiments. Entry:
  `loop-graph-workflows/README.md`.
- **Newsletter Digest & Trends Dashboard** — `newsletter-digest/` and
  `trends-dashboard/`: Python collection and summarization pipeline paired with
  a static Chart.js dashboard. Entries: `newsletter-digest/main.py` and
  `trends-dashboard/index.html`.
- **The Wife Review** — `wife-rating/`: browser-only feedback app with
  shareable links, local history, charts, and CSV export. Entry:
  `wife-rating/index.html`.

Project support:

- `legal-test-docs/` contains shared legal-document test fixtures.
- `clause-remediation-app-plan.md` is the Clause Remediation App implementation
  plan.
- `telegram_bot.py` is the earlier standalone Telegram bot retained for
  reference; current development lives in `agent-team/`.

## Key commands

- Newsletter digest: `cd newsletter-digest && python main.py`
- Newsletter dry run: `cd newsletter-digest && python main.py --dry-run`
- Trends only: `cd newsletter-digest && python main.py --trends-only`
- Backfill digest: `cd newsletter-digest && python main.py --backfill YYYY-MM-DD`
- Agent Team: `cd agent-team && python main.py`
- Legal-doc seed: `cd legal-doc-catalog/seed && pip install -r requirements.txt && python seed_documents.py`
- Static local server: `python -m http.server 8000`
- Tmux workspace: `./tmux-bexperiments.sh`

## Code conventions

- JavaScript uses vanilla ES6 modules, 2-space indentation, kebab-case
  filenames, camelCase variables and functions, and named exports rather than
  default exports.
- Python follows PEP 8, uses 4-space indentation and snake_case filenames, and
  gives modules and functions docstrings.
- Escape HTML content before DOM insertion using the affected project's
  existing `escapeHtml` or `escapeAttr` helpers.
- Keep projects self-contained and avoid build tooling unless a project already
  requires it.

## Working agreements

- Preserve unrelated and uncommitted changes; several experiments may be in
  progress at once.
- Test the affected project locally before proposing a push or deployment.
- Put temporary analysis and generated intermediates in the affected project's
  `work/` folder when needed.
- Put finished user-facing artifacts in the affected project's `outputs/`
  folder when practical.
- Read the affected project's README or local instructions before making
  project-specific changes.

## Credentials and secrets

- Never commit credentials, tokens, OAuth files, or local configuration
  containing secrets.
- Gmail OAuth files: `newsletter-digest/credentials.json` and
  `newsletter-digest/token.json`.
- Agent Team requires `TELEGRAM_BOT_TOKEN` and `ANTHROPIC_API_KEY`.
- Legal Doc Catalog credentials belong in `legal-doc-catalog/config.js`; use
  `config.example.js` as the committed template.
- Legal Doc Catalog seed credentials belong in
  `legal-doc-catalog/seed/.env`, which is ignored by git.

## Deployment

- GitHub Pages serves the `main` branch at
  `https://rbpasternak-tech.github.io/bexperiments/`.
- Newsletter digest data may be auto-committed after scheduled runs.
- Pages changes may become public immediately, so test locally before pushing.

## Obsidian boundary

Rebecca's Obsidian Second Brain is outside this repository and is protected.
Treat it as read-only unless Rebecca explicitly asks for a specific vault edit.
Do not automatically write project summaries, tasks, status updates, links, or
decisions into the vault. Propose the target note and update at handoff. Never
move, rename, delete, restructure, bulk-edit, or change `.obsidian/`
configuration as part of repository work.
