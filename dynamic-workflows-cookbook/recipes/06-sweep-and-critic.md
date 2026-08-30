# Recipe 06 — Multi-modal sweep + completeness critic

## What you'll learn

How to get *coverage* — find the things any single search angle would miss — and then
self-check for the blind spots that even multiple angles share.

## The pattern in one sentence

Run several finders in parallel, each looking through a *different lens* and blind to the
others, then a **critic** reads everything found and hunts for what fell between the searches.

## When to reach for it (and when not to)

**Reach for it when** completeness matters and the thing you're searching has *multiple
dimensions* a single pass would conflate or skip: contract review, security audit, research
("find sources by topic, by author, by date"), incident postmortems.

**Don't reach for it when** the search space is one-dimensional (a single fan-out covers it)
or when "good enough" beats "exhaustive." This is the most thorough pattern in the cookbook
and the one to reserve for "leave nothing on the table" work.

## Two ideas working together

1. **Multi-modal sweep** — instead of N identical finders, give each a *distinct lens*
   (here: money / exit / process). Diversity beats redundancy: identical finders find
   identical things; different lenses cover different ground. Each is **blind to the others**
   so it doesn't anchor on what's already found.
2. **Completeness critic** — a final agent whose only job is *"what did we miss?"* It reads
   the source plus everything the sweep found, and looks specifically for gaps — angles no
   lens covered, issues that fall *between* lenses, whole-document defects.

The critic is the part people skip, and it's the most valuable. A sweep tells you what it
found; only a critic tells you what it *didn't*.

## The script (annotated)

See [`06-sweep-and-critic.workflow.js`](06-sweep-and-critic.workflow.js):

```js
// SWEEP — 3 different lenses at once, each blind to the others
const swept = await parallel(LENSES.map(L => () =>
  agent(`...look ONLY through this lens: ${L.desc}...`, { schema: ISSUE_SCHEMA })))

// CRITIC — reads the source + everything found, hunts the gaps
const critique = await agent(
  `Here is everything 3 single-lens reviewers found:\n${foundList}\n` +
  `Find real problems NONE of them surfaced — especially issues that fall BETWEEN lenses.`,
  { schema: CRITIC_SCHEMA })
```

It's a barrier (`parallel` then a single critic) on purpose: the critic genuinely needs
*all* the sweep results at once to reason about what's missing across them.

## What happened when we ran it

4 agents (3 lenses + 1 critic), ~140s. The sweep found **28 issues** (money 11, exit 8,
process 9). Then the critic found **8 more none of them caught** — and every one was
**structural or cross-clause**, exactly the shared blind spot:

| Critic caught | Why all 3 lenses missed it |
|---|---|
| Heading says "Limitation of Liability"; body imposes *unlimited* liability | A caption-vs-body contradiction is a document-structure defect — no lens reads headings |
| No survival clause — does the uncapped indemnity outlive termination? | Cross-clause: how clause 01 interacts *after* clause 05 |
| No Provider warranty / IP-infringement indemnity | Each lens reviewed what's *present*; this is what's *absent* |
| Delaware law looks engineered to evade home-state auto-renewal statutes | Only visible by connecting clause 02 to clause 03 |
| The accelerated payoff is mathematically unquantifiable | Surfaces only when you compute clause 05 using clause 03's fee terms |
| No severability clause | A whole-document fallback, not a per-clause issue |
| Indemnifying the Provider for its *own* fault may be void as a matter of public policy | An enforceability angle, not the indemnity *procedure* the process lens checked |

The critic's own summary: *"the gaps were structural and cross-clause."* **The lesson:** three
*different* lenses still shared one blind spot — they all read clause-by-clause. The critic
caught the seams between clauses and the whole-document defects no finder was scoped to see.

## Try it yourself

Ask Claude: **"run recipe 06 from the cookbook."** Experiment: add a 4th lens (e.g. "data &
privacy"), or strengthen the critic by running *two* critics with different mandates ("missing
standard protections" vs. "cross-clause interactions") and merging.

## Cost note

~4 agents (3 lenses + 1 critic). Cost = lenses + critics. Cheaper than loop-until-dry and
parallel (the sweep runs at once), but the critic only sees what the sweep surfaced — a weak
sweep gives the critic less to reason against. Invest in diverse lenses first, then the critic.
