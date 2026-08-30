# Clause Remediation App: Legal Document Workflow

> **Note (renamed 2026-06-07):** This project was previously called "managed-agents-demo."
> The name was inaccurate: the implementation is **prompt chaining** (a Flask app making
> direct Claude API calls in a fixed sequence), not Anthropic "managed agents" and not even
> subagents. Renamed to `clause-remediation-app`. The "Managed Agents" framing throughout the
> rest of this plan below is the *original, inaccurate* premise — left as-is for now; the
> project is **parked** and this plan will be rewritten when we revisit it (likely as the
> *hosting layer* on top of the dynamic-workflows orchestration being built in
> `dynamic-workflows-cookbook/`).

## Vision

Demonstrate Claude Managed Agents orchestrating a realistic legal workflow that
spans four systems already built in bexperiments:

1. **Supabase** (Legal Doc Catalog) — the data layer: search, retrieve, and store
   89 legal documents with full-text search, categories, and metadata
2. **Doc Find & Replace** — the processing layer: modify .docx files
   programmatically with find/replace, bracket extraction, and redline generation
3. **Claude for Legal plugins** — the intelligence layer: domain-specific legal
   analysis (NDA review, clause review, escalation flagging, etc.)
4. **Claude Managed Agents API** — the orchestration layer: coordinate
   multi-agent workflows with tool definitions, handoffs, and structured output

The demo shows something a legal team actually needs: taking a policy decision
("we need to update clause X across all agreements of type Y") and executing it
across an entire document portfolio — search, analyze, draft, apply, and QA — with
agents handling each step.

---

## Demo Use Case: Portfolio-Wide Clause Remediation

**Scenario:** A company's outside counsel has advised that the arbitration clause
in all service agreements needs to reference the updated AAA Commercial
Arbitration Rules (2025 edition) instead of the 2013 edition. The legal team
needs to:

1. Find all service agreements in the portfolio
2. Identify which ones contain an arbitration clause
3. Determine if the clause references outdated rules
4. Draft replacement language appropriate to each document's context
5. Apply the changes to the actual .docx files
6. Generate redlines for attorney review

**Why this use case:** It touches every layer of the stack. It's tedious but
high-stakes work that legal teams actually do. And it's the kind of task where
agents genuinely add value — the search + analysis + bulk processing loop is
exactly what's painful to do manually across 89 documents.

---

## Architecture

```
                         ┌──────────────────────┐
                         │   Orchestrator Agent  │
                         │   (Managed Agent)     │
                         │                       │
                         │   Receives user task,  │
                         │   coordinates agents,  │
                         │   reports results      │
                         └──────────┬───────────┘
                                    │
                 ┌──────────────────┼──────────────────┐
                 │                  │                    │
        ┌────────▼────────┐ ┌──────▼──────┐  ┌─────────▼─────────┐
        │  Search Agent   │ │ Legal Agent │  │ Processing Agent  │
        │                 │ │             │  │                   │
        │  Tools:         │ │ Tools:      │  │ Tools:            │
        │  - search_docs  │ │ - analyze   │  │ - find_replace    │
        │  - get_doc      │ │ - draft     │  │ - gen_redline     │
        │  - list_docs    │ │ - review    │  │ - export_clean    │
        │  - filter_docs  │ │ - flag      │  │ - extract_terms   │
        └────────┬────────┘ └──────┬──────┘  └─────────┬─────────┘
                 │                  │                    │
        ┌────────▼────────┐        │           ┌────────▼────────┐
        │   Supabase      │        │           │  Doc Find &     │
        │   (Postgres +   │        │           │  Replace Engine  │
        │    REST API)    │        │           │  (.docx/.pdf)   │
        └─────────────────┘        │           └─────────────────┘
                                   │
                          Claude for Legal
                          domain knowledge
                          (system prompt +
                           few-shot examples)
```

### Design Decisions

**Why three sub-agents instead of one?**

Each agent has a focused tool set and system prompt. The Search Agent knows
Supabase query patterns. The Legal Agent carries domain-specific instructions
from Claude for Legal (clause identification, drafting standards, review
checklists). The Processing Agent handles file I/O and .docx XML manipulation.
Separation keeps context windows clean and tool sets minimal — the Legal Agent
never needs to know about JSZip, and the Processing Agent never needs to reason
about governing law.

**Where does Claude for Legal fit?**

The Claude for Legal plugins (NDA review, clause review, escalation flagging)
are currently Claude Code skills backed by specialized system prompts. For the
Managed Agents demo, we extract their domain logic into the Legal Agent's system
prompt and tool descriptions. This means the Legal Agent carries the same
analytical framework (clause identification, risk flagging, drafting guidelines)
but exposes it through Managed Agent tool definitions rather than Claude Code
slash commands.

Specifically, we can port knowledge from:
- `commercial-legal:review` — contract analysis and clause identification
- `commercial-legal:escalation-flagger` — risk detection patterns
- `commercial-legal:vendor-agreement-review` — service agreement expertise
- `commercial-legal:nda-review` — NDA-specific clause knowledge

**How does Doc Find & Replace integrate?**

The browser-based Doc Find & Replace tool currently works client-side with
JSZip and pdf.js. For the Managed Agents demo, we extract the core logic
(docx-processor.js, replacer.js, bracket-extractor.js) into a Python-callable
module using python-docx. The Processing Agent calls this as a tool, passing
in find/replace pairs and getting back modified .docx files (clean and redline
versions).

---

## Agent Definitions

### 1. Orchestrator Agent

**Role:** Receives the user's high-level task, breaks it into steps, delegates
to sub-agents, aggregates results, and presents a final report.

**System prompt excerpt:**
```
You coordinate legal document remediation workflows. Given a task like
"update arbitration clauses in all service agreements," you:
1. Ask the Search Agent to find relevant documents
2. Ask the Legal Agent to analyze each document for the target clause
3. Ask the Legal Agent to draft replacement language
4. Ask the Processing Agent to apply changes and generate redlines
5. Ask the Legal Agent to QA the changes
6. Compile a summary report with links, change counts, and flags
```

**Tools:** `delegate_to_search`, `delegate_to_legal`, `delegate_to_processing`

### 2. Search Agent

**Role:** Queries Supabase to find and retrieve documents matching criteria.

**Tools:**

| Tool | Description | Maps to |
|------|-------------|---------|
| `search_documents` | Full-text search with highlighted snippets | Supabase RPC `search_documents()` |
| `list_documents` | List all docs, optionally filtered by category/year | Supabase `documents` table query |
| `get_document` | Retrieve full text + metadata for a single doc | Supabase `.select('*').eq('id', id)` |
| `get_document_stats` | Count docs by category, year, or keyword | Supabase aggregate query |

**Supabase connection:** Uses the existing REST API with the anon key + user
auth token. Python `supabase` client wraps each tool.

### 3. Legal Agent

**Role:** Analyzes document text, identifies clauses, drafts replacement
language, reviews changes, and flags risks.

**Tools:**

| Tool | Description | Informed by |
|------|-------------|-------------|
| `identify_clause` | Find a specific clause type in document text, return its location and text | commercial-legal:review |
| `assess_clause` | Determine if a clause meets current standards or needs updating | commercial-legal:escalation-flagger |
| `draft_replacement` | Generate replacement clause language appropriate to context | commercial-legal:vendor-agreement-review |
| `review_redline` | QA a set of changes against the original, flag any issues | commercial-legal:review |
| `classify_document` | Determine document type and key characteristics | commercial-legal:review |

**System prompt** incorporates domain knowledge from Claude for Legal:
- Clause identification patterns (arbitration, governing law, indemnification,
  limitation of liability, force majeure, termination, confidentiality)
- Drafting standards (plain language, consistent defined terms, appropriate
  cross-references)
- Risk flags (one-sided terms, missing protections, non-standard language)
- Review checklists (completeness, consistency, conformity with policy)

### 4. Processing Agent

**Role:** Applies find/replace operations to .docx files and generates output
documents.

**Tools:**

| Tool | Description | Maps to |
|------|-------------|---------|
| `extract_bracketed_terms` | Find [placeholder] terms in document text | bracket-extractor.js logic |
| `apply_replacements` | Apply find/replace pairs to a .docx file | docx-processor.js clean replacements |
| `generate_redline` | Create tracked-changes version of modified .docx | docx-processor.js redline generation |
| `export_batch` | Process multiple documents in batch, return zip | export.js logic |

**Implementation:** Python port of the core JS logic using `python-docx` for
.docx manipulation. The XML-level operations (w:del, w:ins for redlines) port
directly since python-docx exposes the underlying lxml tree.

---

## Demo Workflow: Step by Step

### Step 0: Setup
- Supabase running with 89 seeded documents (done)
- Processing tools ported to Python (to build)
- Agent definitions registered with Managed Agents API (to build)

### Step 1: User Input
```
User: "Find all service and commercial agreements that reference the
AAA Commercial Arbitration Rules. Update any that cite the 2013 edition
to reference the 2025 edition. Generate redlines for my review."
```

### Step 2: Orchestrator Decomposes Task
Orchestrator identifies:
- **Search scope:** category = "Services & Commercial"
- **Target clause:** arbitration clause referencing AAA rules
- **Action:** update "2013" → "2025" edition references
- **Output:** redlined .docx files

### Step 3: Search Agent Finds Documents
```python
# Search Agent calls:
search_documents("arbitration AAA")
# → Returns docs with highlighted snippets showing AAA references

list_documents(category="Services & Commercial")
# → Returns all 6 service/commercial agreements + 2 undated
```

### Step 4: Legal Agent Analyzes Each Document
For each document returned:
```python
# Legal Agent calls:
identify_clause(doc_text, clause_type="arbitration")
# → Returns: { found: true, text: "...AAA Commercial Arbitration Rules
#   (2013 edition)...", location: "Section 12.3", confidence: 0.95 }

assess_clause(clause_text, standard="AAA 2025 edition")
# → Returns: { needs_update: true, reason: "References 2013 edition",
#   risk_level: "medium" }
```

### Step 5: Legal Agent Drafts Replacements
```python
draft_replacement(
  original_clause="...disputes shall be resolved by binding arbitration
    administered by the American Arbitration Association under its
    Commercial Arbitration Rules (2013 edition)...",
  target_standard="AAA Commercial Arbitration Rules, effective
    September 1, 2025",
  context="Master Services Agreement between technology vendor and
    enterprise client"
)
# → Returns replacement text with appropriate language
```

### Step 6: Processing Agent Applies Changes
```python
apply_replacements(
  doc_id="abc-123",
  replacements=[
    { find: "Commercial Arbitration Rules (2013 edition)",
      replace: "Commercial Arbitration Rules, effective September 1, 2025" }
  ]
)
# → Returns modified .docx (clean version)

generate_redline(doc_id="abc-123", replacements=[...])
# → Returns .docx with tracked changes (w:del + w:ins markup)
```

### Step 7: Legal Agent QAs Changes
```python
review_redline(
  original_text="...",
  modified_text="...",
  intended_changes=["Update AAA rules reference from 2013 to 2025"]
)
# → Returns: { approved: true, notes: "Change is scoped correctly.
#   No unintended modifications to surrounding clause language." }
```

### Step 8: Orchestrator Reports Results
```
Remediation Complete:
- Searched: 89 documents in portfolio
- Matched: 6 service/commercial agreements
- Analyzed: 6 documents for arbitration clauses
- Found outdated: 4 documents referencing 2013 AAA rules
- Updated: 4 documents
- Redlines ready: 4 .docx files in /output/redlines/
- Clean versions: 4 .docx files in /output/clean/
- QA passed: 4/4

Documents updated:
1. Master_Services_Agreement.docx — Section 12.3
2. Professional_Services_Agreement.docx — Section 9.1
3. Consulting_Services_Agreement_2017.docx — Section 14
4. Supply_Agreement_2019.docx — Section 11.2

No flags raised. Ready for attorney review.
```

---

## What Needs to Be Built

### Phase 1: Python Tool Layer (foundation)
Build Python modules that wrap existing capabilities as callable functions:

1. **`tools/supabase_tools.py`** — Wraps Supabase queries
   - `search_documents(query)` → uses existing RPC
   - `list_documents(category?, year?)` → filtered select
   - `get_document(id)` → full document retrieval
   - Already have the Python client working (used in seed script)

2. **`tools/docx_tools.py`** — Ports Doc Find & Replace logic to Python
   - `extract_bracketed_terms(docx_path)` → port bracket-extractor.js
   - `apply_replacements(docx_path, replacements)` → port docx-processor.js
   - `generate_redline(docx_path, replacements)` → port tracked changes logic
   - Use `python-docx` + `lxml` for XML manipulation

3. **`tools/legal_tools.py`** — Claude API calls with legal domain prompts
   - `identify_clause(text, clause_type)` → structured extraction
   - `assess_clause(clause_text, standard)` → compliance check
   - `draft_replacement(original, target, context)` → drafting
   - `review_redline(original, modified, intent)` → QA
   - System prompts drawn from Claude for Legal plugin patterns

### Phase 2: Managed Agents Wiring
Register tools and agents with the Claude API:

4. **`agents/definitions.py`** — Agent configs
   - Tool schemas (JSON Schema for each tool)
   - System prompts per agent
   - Orchestration logic

5. **`agents/orchestrator.py`** — Main entry point
   - Takes user input
   - Runs the multi-agent loop
   - Collects and formats results

6. **`agents/run_demo.py`** — Demo runner
   - Hardcoded example inputs for the demo scenario
   - Pretty-prints each step with timing
   - Saves output artifacts (redlines, report)

### Phase 3: Polish & Presentation
7. **Output artifacts**
   - Redlined .docx files in output directory
   - JSON report with per-document details
   - Summary markdown for display

8. **Demo script**
   - Talking points for each step
   - Fallback if API is slow (pre-cached responses)
   - Before/after document comparison

---

## File Structure

```
bexperiments/
├── legal-doc-catalog/          # Existing — Supabase frontend
│   ├── config.js               # Supabase credentials
│   ├── schema.sql              # Database schema
│   └── seed/                   # Seed script
│
├── doc-find-replace/           # Existing — browser-based tool
│   └── js/
│       ├── docx-processor.js   # Core logic to port
│       ├── replacer.js         # Find/replace engine
│       └── bracket-extractor.js
│
├── clause-remediation-app/        # New — the demo project
│   ├── tools/
│   │   ├── supabase_tools.py   # Supabase query wrappers
│   │   ├── docx_tools.py       # Python port of doc processing
│   │   └── legal_tools.py      # Claude API legal analysis
│   ├── agents/
│   │   ├── definitions.py      # Agent + tool schemas
│   │   ├── orchestrator.py     # Multi-agent coordination
│   │   └── run_demo.py         # Demo entry point
│   ├── output/                 # Generated artifacts
│   │   ├── redlines/
│   │   └── clean/
│   ├── .env                    # API keys (gitignored)
│   ├── requirements.txt
│   └── README.md
│
└── clause-remediation-app-plan.md # This file
```

---

## Claude for Legal Plugin Mapping

Shows which existing plugins inform each agent capability:

| Agent Capability | Plugin Source | What We Extract |
|---|---|---|
| Clause identification | `commercial-legal:review` | Patterns for finding specific clause types in unstructured text |
| Risk assessment | `commercial-legal:escalation-flagger` | Criteria for flagging non-standard or risky terms |
| Service agreement expertise | `commercial-legal:vendor-agreement-review` | Domain knowledge about common service agreement structures |
| NDA clause knowledge | `commercial-legal:nda-review` | Confidentiality clause patterns, common deviations |
| Document classification | `commercial-legal:review` | Heuristics for identifying document types from content |
| Drafting standards | `commercial-legal:review` | Plain language guidelines, defined term conventions |

---

## Open Questions

1. **Managed Agents API access:** Do we have API access to Managed Agents, or
   do we simulate the orchestration pattern using standard tool_use with the
   Claude API? (The multi-agent pattern works either way — Managed Agents just
   adds lifecycle management and monitoring.)

2. **Document storage for processing:** The Supabase catalog stores extracted
   text but not the original .docx files. For the Processing Agent to modify
   actual documents, we need either:
   - (a) Pull .docx files from the local `Dummy docs` folder by filename match
   - (b) Add Supabase Storage to host the original .docx files
   - (c) For the demo, use the local folder (simpler)

3. **Scope of the demo:** Full end-to-end with real API calls, or a narrated
   walkthrough with some steps pre-computed? Real calls are more impressive but
   slower and more expensive.

4. **Audience:** Is this for a conference talk, a blog post, internal demo,
   or the book? The format affects how much we invest in polish vs. substance.
