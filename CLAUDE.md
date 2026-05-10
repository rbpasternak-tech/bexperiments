# bexperiments

Personal monorepo (parent repo) for all projects and experiments. Each project lives in its own subfolder. Deployed via GitHub Pages.

## Repo Structure

This is a monorepo — all projects share one git repo. New projects go in new subfolders at the root (e.g., `my-new-project/`). Each subfolder is self-contained.

## Current Projects

- **habit-tracker/** — Vanilla JS PWA for daily habit tracking. Uses localStorage, service worker for offline. Entry: `habit-tracker/index.html`
- **newsletter-digest/** — Python pipeline: fetches Gmail newsletters + RSS feeds, summarizes with Claude API, emails HTML digest. Entry: `newsletter-digest/main.py`
- **trends-dashboard/** — Static JS dashboard visualizing digest data with Chart.js. Entry: `trends-dashboard/index.html`
- **doc-find-replace/** — Browser-based document find-and-replace tool for .docx and .pdf files. Vanilla JS, IndexedDB persistence. Includes `txt_to_docx.py` helper for batch-converting test files. Entry: `doc-find-replace/index.html`
- **legal-doc-catalog/** — Vanilla JS app backed by Supabase for cataloging legal documents with full-text search. Python seed script for importing .docx files. Entry: `legal-doc-catalog/index.html`
- **telegram_bot.py** — Standalone Telegram bot script

## Adding a New Project

1. Create a new folder at the repo root: `mkdir my-new-project`
2. Build inside that folder — keep it self-contained
3. Update the "Current Projects" list above with a one-liner
4. Update `README.md` with a description and links for the new project
5. Commit and push

## Tech & Conventions

- JavaScript: vanilla ES6 modules, 2-space indent, `kebab-case.js` files, `camelCase` vars/functions
- Python: PEP 8, 4-space indent, `snake_case.py` files, docstrings on all functions
- No build tools — everything runs as-is (static HTML/JS or Python scripts)
- Chart.js v4 loaded from CDN for dashboard visualizations

## Key Commands

- **Run newsletter digest:** `cd newsletter-digest && python main.py`
- **Dry run (no email):** `cd newsletter-digest && python main.py --dry-run`
- **Trends only:** `cd newsletter-digest && python main.py --trends-only`
- **Backfill past week:** `cd newsletter-digest && python main.py --backfill YYYY-MM-DD`
- **Serve locally:** `python -m http.server 8000` (from repo root)
- **Seed legal docs:** `cd legal-doc-catalog/seed && pip install -r requirements.txt && python seed_documents.py`

## Credentials & Secrets

- Gmail OAuth: `newsletter-digest/credentials.json` + `newsletter-digest/token.json` (never commit)
- Anthropic API key: `ANTHROPIC_API_KEY` env var
- Telegram bot token: stored in `.claude/settings.local.json` (never commit)
- Supabase credentials: `legal-doc-catalog/config.js` (never commit, use `config.example.js` as template)

## Deployment

- GitHub Pages serves from `main` branch: `https://rbpasternak-tech.github.io/bexperiments/`
- Dashboard data (JSON) auto-committed after each digest run via launchd
- Always test locally before pushing — Pages builds are public immediately

## Working in This Repo

- Each sub-project is self-contained — don't create cross-project imports
- When editing JS, use `export function` (named exports), not default exports
- Python modules should have module-level docstrings
- HTML content must be escaped before DOM insertion (use existing `escapeHtml`/`escapeAttr` helpers)
