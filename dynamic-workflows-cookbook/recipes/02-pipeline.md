# Recipe 02 — Pipeline

## What you'll learn

What to do when fan-out *can't* help: tasks where step 2 needs step 1's answer — while
still not making your items wait in line for each other.

## The pattern in one sentence

Each item flows through ordered stages (step 2 depends on step 1), and items move through
**independently** — no barrier forcing everyone to finish a stage before anyone starts the next.

## When to reach for it (and when not to)

**Reach for it when** each item needs a *sequence* of steps where later steps depend on
earlier ones: analyze → draft, extract → classify → summarize, find → verify. Fan-out can't
express the dependency; a pipeline can.

**Don't reach for it when** the steps are independent (just fan out — recipe 01), or when a
stage genuinely needs *all* items from the previous stage at once before it can start (e.g.
dedup across everything, or "stop if zero found"). That cross-item dependency is the one case
you want a *barrier* instead — see the note below.

## Fan-out vs. pipeline (the core distinction)

|  | Fan-out (01) | Pipeline (02) |
|---|---|---|
| Steps per item | One | Several, in order |
| Step 2 needs step 1? | No | **Yes** |
| Items wait for each other? | No | No |

A pipeline is **not** "fan out to analyze, wait for all, then fan out to fix." That waiting
("barrier") wastes time — a clause that finished analysis early shouldn't sit idle while a
slow one catches up. `pipeline()` removes the barrier: each clause goes straight from its own
analysis into its own fix.

## The script (annotated)

See [`02-pipeline.workflow.js`](02-pipeline.workflow.js). The pattern is one call with two
stage functions:

```js
const results = await pipeline(
  CLAUSES,
  (name)     => agent(`...analyze ${name}, find the problem...`, { schema: ANALYZE_SCHEMA }),
  (analysis) => agent(`...problem was "${analysis.problem}", draft a fix...`, { schema: FIX_SCHEMA })
)
```

- **Stage 2 receives stage 1's return value** (`analysis`). That hand-off *is* the
  dependency — the fix prompt literally includes the problem the analysis found.
- **No barrier**: as soon as one clause finishes stage 1, it enters stage 2 — while other
  clauses are still in stage 1.
- A stage that throws drops just that item to `null` (the others keep going), so we
  `.filter(Boolean)` at the end.

## What happened when we ran it

10 agents (5 analyze + 5 fix), **34 seconds**. It drafted fixes for the 3 risky clauses and
passed the 2 standard ones through untouched:

| Clause | Stage 1 found | Stage 2 drafted |
|---|---|---|
| 01 Liability | Uncapped liability + one-way indemnity | Mutual cap at trailing-12-mo fees, mutual carve-outs (fraud, confidentiality), **two-way** indemnity |
| 02 Governing law | none | *no change needed* |
| 03 Auto-renewal | Unlimited discretionary price hikes | Increase capped at greater of CPI or 5%, 60-day notice, consent required above cap |
| 04 Notices | none | *no change needed* |
| 05 Termination | One-sided exit, no customer recourse | Mutual termination + cure periods, **pro-rata refunds**, no acceleration, survival clause |

The fixes are real redline language, not just flags — and stage 2 could only write them
because stage 1 handed over the specific problem. That hand-off is the whole point.

## Try it yourself

Ask Claude: **"run recipe 02 from the cookbook."** Watch with `/workflows` — you'll see
`fix:` agents start *before* every `analyze:` agent has finished. That's the no-barrier
behavior you can't get from two separate fan-outs.

## Cost note

~10 agents (5 items × 2 stages) on short inputs. Cost scales with items × stages: 50 clauses
× 2 stages ≈ 100 agents. Add stages only when each earns its keep — every stage multiplies
the agent count.
