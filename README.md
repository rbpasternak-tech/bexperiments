# bexperiments

Rebecca's personal monorepo for small applications, automations, and learning
experiments. The canonical local path is
`~/Documents/GitHub/bexperiments/`; `~/bexperiments` is a compatibility
shortcut to the same repository.

## Projects

Projects are listed alphabetically by their descriptive name. Each retained
project lives in a self-contained root-level folder.

### Agent Team

[`agent-team/`](agent-team/)

A Telegram bot hosting a team of Claude-powered literary personas that plan,
nudge, set reminders, and read newsletter-digest data.

### Clause Remediation App

[`clause-remediation-app/`](clause-remediation-app/)

A Flask prototype for reviewing and remediating contract clauses with a fixed,
multi-step AI workflow.

### Doc Find & Replace

[`doc-find-replace/`](doc-find-replace/) ·
[Live app](https://rbpasternak-tech.github.io/bexperiments/doc-find-replace/)

A browser-based bulk editor for `.docx` and `.pdf` files, with IndexedDB
persistence, placeholder extraction, and clean or tracked-changes exports.

### Dynamic Workflows Cookbook

[`dynamic-workflows-cookbook/`](dynamic-workflows-cookbook/)

A learn-by-watching collection of coordinated-agent workflow patterns, run
logs, clause examples, and an interactive pattern board.

### Habit Tracker

[`habit-tracker/`](habit-tracker/) ·
[Live app](https://rbpasternak-tech.github.io/bexperiments/habit-tracker/)

A vanilla JavaScript PWA for daily habit tracking, monthly grids, statistics,
and offline use.

### Legal Doc Catalog

[`legal-doc-catalog/`](legal-doc-catalog/) ·
[Live app](https://rbpasternak-tech.github.io/bexperiments/legal-doc-catalog/)

A Supabase-backed catalog for legal documents with category browsing,
full-text search, highlighted snippets, and a Python import utility.

### Loop & Graph Workflows

[`loop-graph-workflows/`](loop-graph-workflows/)

Two Claude Code workflow experiments: a verifier-controlled goal loop and a
dependency graph whose agents run as soon as their inputs are ready.

### Newsletter Digest & Trends Dashboard

[`newsletter-digest/`](newsletter-digest/) ·
[`trends-dashboard/`](trends-dashboard/) ·
[Live dashboard](https://rbpasternak-tech.github.io/bexperiments/trends-dashboard/)

A Python pipeline that gathers and summarizes newsletters and RSS feeds,
paired with a static Chart.js dashboard for weekly technology and legal-tech
trends.

### The Wife Review

[`wife-rating/`](wife-rating/) ·
[Live app](https://rbpasternak-tech.github.io/bexperiments/wife-rating/)

A tongue-in-cheek, browser-only feedback app with shareable review links,
local history, trend charts, and CSV export.

## Project support

- [`legal-test-docs/`](legal-test-docs/) contains test fixtures shared by the
  legal-document experiments; it is not a separate product.
- [`clause-remediation-app-plan.md`](clause-remediation-app-plan.md) is the
  implementation plan for the Clause Remediation App.

## Repository tools

- [`CHEATSHEET.md`](CHEATSHEET.md) and `CHEATSHEET.pdf` provide the local Claude
  Code command reference.
- [`claude-code-new-project-checklist.md`](claude-code-new-project-checklist.md)
  and [`claude-code-scaffold.sh`](claude-code-scaffold.sh) help start new
  projects consistently.
- [`tmux-bexperiments.sh`](tmux-bexperiments.sh) opens a tmux workspace for the
  monorepo; [`watchtower.py`](watchtower.py) monitors its Claude sessions.
- `telegram_bot.py` is the earlier standalone Telegram bot retained for
  reference; current bot development lives in `agent-team/`.

## Filing rules

- Keep code projects in this repository, each in a descriptive root-level
  folder. Do not use names such as `my-new-project` or `untitled`.
- Keep drafts and generated intermediates in the affected project's `work/`
  folder when needed.
- Keep finished user-facing artifacts in the affected project's `outputs/`
  folder when practical.
- Keep Git branches and pull requests attached to this repository; do not
  create separate local PR folders.
- Update this catalog and the project inventory in `CLAUDE.md` together when a
  retained project is added, removed, or renamed.

## Development workspace

Run `./tmux-bexperiments.sh` from the repository root to open the standard tmux
workspace. Detach with `Ctrl-b d` and reattach with
`tmux attach -t bexperiments`.
