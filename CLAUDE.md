# bexperiments

Personal monorepo for tools and experiments, deployed via GitHub Pages.

## Projects

- **habit-tracker/** — Vanilla JS PWA for daily habit tracking. Uses localStorage, service worker for offline. Entry: `habit-tracker/index.html`
- **newsletter-digest/** — Python pipeline: fetches Gmail newsletters + RSS feeds, summarizes with Claude API, emails HTML digest. Entry: `newsletter-digest/main.py`
- **trends-dashboard/** — Static JS dashboard visualizing digest data with Chart.js. Entry: `trends-dashboard/index.html`
- **telegram_bot.py** — Standalone Telegram bot script

## Tech & Conventions

- JavaScript: vanilla ES6 modules, 2-space indent, `kebab-case.js` files, `camelCase` vars/functions
- Python: PEP 8, 4-space indent, `snake_case.py` files, docstrings on all functions
- No build tools — everything runs as-is (static HTML/JS or Python scripts)
- Chart.js v4 loaded from CDN for dashboard visualizations

## Key Commands

- **Run newsletter digest:** `cd newsletter-digest && python main.py`
- **Dry run (no email):** `cd newsletter-digest && python main.py --dry-run`
- **Trends only:** `cd newsletter-digest && python main.py --trends-only`
- **Serve locally:** `python -m http.server 8000` (from repo root)

## Credentials & Secrets

- Gmail OAuth: `newsletter-digest/credentials.json` + `newsletter-digest/token.json` (never commit)
- Anthropic API key: `ANTHROPIC_API_KEY` env var
- Telegram bot token: stored in `.claude/settings.local.json` (never commit)

## Deployment

- GitHub Pages serves from `main` branch: `https://rbpasternak-tech.github.io/bexperiments/`
- Dashboard data (JSON) auto-committed after each digest run via launchd
- Always test locally before pushing — Pages builds are public immediately

## Working in This Repo

- Each sub-project is self-contained — don't create cross-project imports
- When editing JS, use `export function` (named exports), not default exports
- Python modules should have module-level docstrings
- HTML content must be escaped before DOM insertion (use existing `escapeHtml`/`escapeAttr` helpers)
