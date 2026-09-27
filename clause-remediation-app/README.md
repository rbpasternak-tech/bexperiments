# Clause Remediation App

Flask prototype that updates one clause type across a portfolio of legal
documents. It chains direct Claude API calls in a fixed sequence:

1. **Search** — full-text search (plus an optional category listing) against the
   Supabase `documents` table from [Legal Doc Catalog](../legal-doc-catalog/).
2. **Analyze** — Claude identifies the target clause in each document and
   decides whether it meets the new standard.
3. **Draft** — Claude drafts replacement language as a find/replace pair.
4. **Process** — the local `.docx` is rewritten twice: a clean copy and a
   tracked-changes redline (body paragraphs and table cells).
5. **QA** — Claude reviews the original vs. modified excerpt.

The dashboard streams each step live over Server-Sent Events. The original
design notes are in [`../clause-remediation-app-plan.md`](../clause-remediation-app-plan.md)
(its "Managed Agents" framing is out of date; see the note at the top of that
file).

## Setup

```bash
cd clause-remediation-app
pip install -r requirements.txt
```

Create `clause-remediation-app/.env` (gitignored by the repository root
`.gitignore`); it is loaded by both `server.py` and `agents/run_demo.py`.

| Variable | Required | Purpose |
| --- | --- | --- |
| `SUPABASE_URL` | yes | Legal Doc Catalog Supabase project URL. |
| `SUPABASE_ANON_KEY` | yes, unless `SUPABASE_SERVICE_KEY` is set | Project key. Used if `SUPABASE_SERVICE_KEY` is unset. |
| `SUPABASE_SERVICE_KEY` | optional | Used instead of the anon key when set. Queries still run as the signed-in seed user under row-level security, so the anon key is enough. |
| `SEED_EMAIL`, `SEED_PASSWORD` | yes | Catalog user the app signs in as; only that user's documents are visible. Same account used by `legal-doc-catalog/seed/`. |
| `ANTHROPIC_API_KEY` | yes | Read by the Anthropic SDK for the Claude calls. |
| `CLAUDE_MODEL` | optional | Model for all Claude calls. Default `claude-sonnet-5`. |
| `DOCS_DIR` | optional | Folder holding the source `.docx` files. Default `~/Dummy docs` (the path on Rebecca's machine). Scanned recursively and matched by filename, so it should be the same tree the catalog was seeded from. |

Documents must already be in Supabase (run the Legal Doc Catalog seed script)
and the matching `.docx` files must exist under `DOCS_DIR`; documents whose
file is not found locally are reported as skipped.

## Running

Dashboard (Flask dev server, bound to `127.0.0.1:5001`):

```bash
python server.py
# open http://127.0.0.1:5001/
```

Command-line demo (AAA 2013 to AAA 2024 arbitration rules, filtered to
"Services & Commercial"):

```bash
python agents/run_demo.py
```

Each run makes several paid Claude API calls per document.

## Output

Generated files are written to `output/` and overwritten on every run:

- `output/clean/<filename>.docx` — replacements applied directly.
- `output/redlines/<filename>.docx` — the same changes as tracked
  insertions/deletions.

`output/` is generated and ignored by git (`clause-remediation-app/.gitignore`).
Note that the clean copy collapses each changed paragraph's text into its
first run, so mixed formatting inside a changed paragraph is lost.

## Known behavior

- **Category filter is a union, not an intersection.** When a category filter
  is set, the documents analyzed are *full-text search hits* **plus** *every
  document in the category*. Search hits outside the category are still
  analyzed, and category documents without a search hit are analyzed too.
- If two files under `DOCS_DIR` share a filename, the first one in sorted path
  order is used.
- The server has no authentication and is intended for local use only.
  `/api/run` rejects browser requests marked as cross-site.

## Layout

- `server.py` — Flask app: dashboard, `/api/stats`, `/api/run` (SSE).
- `agents/orchestrator_stream.py` — generator used by the dashboard.
- `agents/orchestrator.py`, `agents/run_demo.py` — command-line version.
- `tools/supabase_tools.py` — Supabase queries.
- `tools/legal_tools.py` — Claude prompts and JSON parsing.
- `tools/docx_tools.py` — `.docx` find/replace, redlines, and file index.
- `static/` — dashboard HTML, CSS, and JavaScript.
