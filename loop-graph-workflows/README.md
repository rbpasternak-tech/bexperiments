# Loop & Graph — dynamic workflow experiments

Two hand-rolled dynamic workflows, built after the cookbook
([`dynamic-workflows-cookbook/`](../dynamic-workflows-cookbook/)) and inspired by the
"Graph Engineering" article (agents wired by *true dependencies*, not artificial
sequential order). Both run against the cookbook's clause corpus via Claude Code's
**Workflow tool** — ask Claude "run the loop/graph workflow in
`loop-graph-workflows`".
They are not standalone Node scripts.

## `loop.workflow.js` — goal loop

Same shape as cookbook recipe 07: **draft → independent verify → feed failures back →
repeat** until the verifier signs off (guards: 4-iteration cap, stuck-detection).
Target: the provider-friendly auto-renewal clause (`corpus/clauses/03-auto-renewal.txt`).

**Run result:** passed on iteration 1 — 2 agents, ~54k tokens, 17s. The rewrite cut the
non-renewal notice from 90 → 30 days, capped fee increases at the lesser of 5% or CPI
with 60 days' notice, and added a penalty-free opt-out after any increase notice.

## `graph.workflow.js` — dependency graph ("graph engineering")

The step past fan-out (no deps) and pipeline (linear deps): **agents are nodes,
promises are edges**, and each node fires the moment *its* parents finish — no global
barriers.

```
read:liability ──┐
read:termination ─┼──▶ join:risk ─────┐
                  │                   │
read:renewal ─────┼──▶ join:timeline ─┼──▶ memo
read:notices ─────┘                   │
read:law ────────────▶ check:law ─────┘
```

The termination reader feeds *two* downstream joins — that shared edge is what makes
this a graph, not a pipeline. The governing-law chain runs fully independently of the
other two branches.

**Run result:** 9/9 agents, ~245k tokens, 62s. Output: a GC-ready memo ranking the top
3 risks (uncapped no-fault indemnity → one-sided termination with fee acceleration →
Delaware forum), key dates to calendar, and prioritized redlines.

## The two patterns in one line each

- **Loop** = convergence: repeat until a verifier with the power to say "no" says "yes".
- **Graph** = scheduling: express only the real data dependencies and let everything
  else run concurrently.
