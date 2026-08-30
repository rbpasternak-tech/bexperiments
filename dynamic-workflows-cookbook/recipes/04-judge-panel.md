# Recipe 04 — Judge panel

## What you'll learn

How to get a *high-quality* answer to an open-ended problem that has no single right answer —
by exploring several angles and combining the best of them, instead of trusting one attempt.

## The pattern in one sentence

Generate several independent attempts from *different angles*, have a panel of judges pick the
best, then synthesize a final that grafts in the strongest ideas from the runners-up.

## When to reach for it (and when not to)

**Reach for it when** the task is open-ended and quality matters: drafting, design proposals,
naming, architecture options, "what's the best way to..." One agent anchors on its first idea;
a panel explores the space.

**Don't reach for it when** there's a single verifiable correct answer (use plain work, or
*verify* it — recipe 03), or when any reasonable answer is fine (just ask once). The panel
costs several drafts + several judges — spend it when the *best* answer is worth real money.

## Verify vs. judge panel (don't mix them up)

- **Adversarial verify (03)** asks of ONE answer: *"is this right?"* → keep or kill.
- **Judge panel (04)** asks of SEVERAL answers: *"which is best, and can we combine them?"*
  → select and synthesize.

One filters; the other explores and merges.

## The three moves that make it work

1. **Divergent generation** — the candidates come from *deliberately different angles*
   (here: customer-protective / balanced / minimal-change). Same prompt three times would
   just give you three near-copies; different angles actually explore the solution space.
2. **Independent judging** — judges see all candidates but not each other, then vote. A
   unanimous vote is itself a confidence signal.
3. **Synthesis, not just selection** — the final step starts from the winner and *grafts in*
   the best ideas from the others, so the result can beat every individual candidate.

## The script (annotated)

See [`04-judge-panel.workflow.js`](04-judge-panel.workflow.js). Three phases:

```js
const drafts    = await parallel(ANGLES.map(a => () => agent(`...${a.instruction}...`, {schema: DRAFT_SCHEMA})))
const judgments = await parallel([1,2,3].map(j => () => agent(`...pick the best of:\n${ballot}`, {schema: JUDGE_SCHEMA})))
// tally votes (plain code) -> winnerId
const final     = await agent(`Start from winner ${winnerId}, graft the best of the rest...`, {schema: SYNTH_SCHEMA})
```

Note the **vote tally is plain JavaScript**, not an agent — counting is deterministic, so don't
pay an agent to do it.

## What happened when we ran it

7 agents (3 drafts + 3 judges + 1 synthesis), ~79 seconds. We redrafted the one-sided
**liability clause** from three angles. The panel was **unanimous, 3–0 for B (balanced-market)**
— the only fully mutual, market-standard draft, the version both sides would actually sign. A
was dinged as too customer-skewed; C as too terse (its cap swallowed the indemnity).

Then synthesis made it better than B alone by grafting in five things from A:

- death/personal-injury carve-out + payment-obligations exclusion
- "whether in contract, tort, or otherwise" theory-of-liability language
- an IP-infringement indemnity trigger — **recast as mutual** (A had it provider-only)
- the "agreed allocation of risk / essential basis of the bargain" enforceability sentence
- "affiliates" added to the indemnified parties

It took nothing from C (its defects were what the judges flagged) and added a materiality-of-
prejudice qualifier on the notice requirement as independent polish. **The final clause beats
all three candidates** — that's the payoff of synthesis over plain selection.

## Try it yourself

Ask Claude: **"run recipe 04 from the cookbook."** Experiment: change the three `ANGLES` (e.g.
add a "plain-English / readable" angle), add a 4th judge, or point `FILE` at a different
clause. Watch whether the panel stays unanimous or splits — a split vote is where synthesis
earns its keep most.

## Cost note

~7 agents (3 + 3 + 1). Cost = candidates + judges + 1. More angles explore more; more judges
reduce a fluke vote. For most tasks 3 + 3 is plenty. This is the priciest recipe so far per
run — reserve it for answers where "best" genuinely matters.
