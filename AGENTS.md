# bexperiments

This is Rebecca's personal monorepo. Its canonical local path is `/Users/rebeccapasternak/Documents/GitHub/bexperiments/`; `/Users/rebeccapasternak/bexperiments` is a compatibility shortcut.

`AGENTS.md` and `CLAUDE.md` must remain behaviorally aligned. `CLAUDE.md` is the detailed project inventory and command reference. Apply the same repository, safety, testing, output, and Obsidian-boundary rules in both tools.

## Repository structure

- All projects share one git repository and live in self-contained root-level subfolders.
- New projects go in new root-level folders. Update the project inventory in `CLAUDE.md` and the links/descriptions in `README.md` if the project is retained.
- Do not create cross-project imports without explicit approval.

## Documentation roles

- `README.md` is the human-facing catalog of retained projects and repository tools.
- `AGENTS.md` is the canonical shared behavior and safety policy for coding agents.
- `CLAUDE.md` contains the matching behavior rules plus detailed project commands,
  credentials guidance, and deployment notes for Claude Code.
- When a retained project is added, removed, or renamed, update the catalog in
  `README.md` and the inventory in `CLAUDE.md` together.
- Git branches and pull requests belong to this repository; do not create local
  folders that duplicate PRs.

## Working agreements

- Preserve unrelated and uncommitted changes. This repository often has several experiments in progress at once.
- Read `CLAUDE.md` and `README.md` for the current project inventory, commands, credentials guidance, and deployment notes.
- Never commit credentials, tokens, OAuth files, or local configuration containing secrets.
- Test the affected project locally before proposing a push or deployment. GitHub Pages changes may become public immediately.
- Put temporary analysis and generated intermediates in a project-local `work/` folder when needed. Put user-facing finished artifacts in the relevant project's `outputs/` folder.
- JavaScript uses vanilla ES6 modules, 2-space indentation, kebab-case filenames, camelCase variables/functions, and named exports rather than default exports.
- Python follows PEP 8, uses 4-space indentation and snake_case filenames, and gives modules and functions docstrings.
- Escape HTML content before DOM insertion using the project's existing `escapeHtml` or `escapeAttr` helpers.

## Obsidian boundary

Rebecca's Obsidian Second Brain is outside this repository and is protected.

- Treat the vault as read-only unless Rebecca explicitly asks for a specific Obsidian edit in the current task.
- Do not automatically write project summaries, tasks, status, links, or decisions into the vault. Propose the target note and short update at handoff.
- Never move, rename, delete, restructure, bulk-edit, or change `.obsidian/` configuration as part of repository work.
- Existing scheduled Obsidian workflows are separate and may perform only the writes defined in their own task files.
