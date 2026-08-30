# Recipe 07 — Goal loop (loop engineering)

## What you'll learn

The pattern both Anthropic and OpenAI converged on in 2026: **stop hand-crafting the perfect
prompt; write a loop that does the work, checks it, and repeats until a goal is met.** The
agent loop becomes the unit of work — you engineer the *loop*, not the *prompt*.

## The pattern in one sentence

Draft → have an independent verifier that *can say no* check it against a checkable goal →
feed the failures back into the next draft → repeat until it passes or a guard fires.

## When to reach for it (and when not to)

**Reach for it when** there's a **verifiable definition of done** and the first try usually
won't hit it: "fix this until the tests pass," "rewrite this clause until it meets the
playbook," "make the build green." The loop converges; you don't have to nail the prompt.

**Don't reach for it when** one pass is genuinely enough (just ask once), or when you can't
state a checkable goal — *a loop with no way to check "done" can't know when to stop.* If you
need *coverage* of an unknown-size result set instead of convergence on a goal, that's
loop-until-dry (05), not this.

## Loop-until-dry (05) vs. goal loop (07) — don't mix them up

- **Loop-until-dry (05)** loops for **discovery**. Stop signal: *"rounds stopped finding
  anything new."* You don't know how much is out there.
- **Goal loop (07)** loops for **convergence**. Stop signal: *"the verifier signed off."* You
  know exactly what done looks like; you're driving toward it.

One drains a well; the other climbs to a target.

## Why the verifier is the whole game

The blogs put it bluntly: *"a loop with nothing to push back is the agent agreeing with itself
on repeat."* The drafter will always think its work is fine. The loop is only trustworthy
because an **independent** agent holds the acceptance criteria and can reject — and its
rejection becomes the next draft's instructions. Generate-only loops drift; generate-and-check
loops converge.

## The three hard stops (or you get infinite loops and billing surprises)

Every production loop needs all three. This recipe has all three:

1. **Iteration cap** (`MAX_ITERS`) — the dumb-but-essential backstop. Nothing loops forever.
2. **No-progress detection** — if the verifier returns the *same* failures two rounds running,
   the loop is stuck; more iterations won't help, so bail and say so.
3. **Budget ceiling** — don't *start* a round you can't afford. Guards on `budget.total` so it
   only bites when you set a token target for the turn (e.g. "+200k").

And the loop reports *why* it stopped (`outcome`) — `passed`, `no-progress`, `iter-cap`, or
`budget-ceiling` — so a loop that ran out of road never masquerades as a loop that succeeded.

## The script (annotated)

See [`07-goal-loop.workflow.js`](07-goal-loop.workflow.js). The shape is a `while` loop with a
draft step, a verify gate, and a decide step:

```js
while (iter < MAX_ITERS) {
  if (budget.total && budget.remaining() < MIN_BUDGET) break   // hard stop 3
  draft   = await agent(revisePrompt(draft, lastFailures), { schema: DRAFT_SCHEMA })
  verdict = await agent(checkPrompt(draft), { schema: VERDICT_SCHEMA })  // the gate that says no
  if (verdict.passed) { outcome = 'passed'; break }            // goal met → exit
  if (failures === lastFailures && ++noProgress >= 2) break    // hard stop 2
  lastFailures = failures                                      // feed forward into next draft
}
```

Like loop-until-dry, it's **sequential** — each draft needs the previous verdict to know what
to fix. The two agents per round (drafter + verifier) are deliberately *not* the same agent:
that independence is what lets the gate genuinely push back.

## What happened when we ran it

Run `wf_59f97408-667` — 2 agents, ~43k tokens, ~24s. The target clause violated **all four**
criteria (unlimited liability, one-sided indemnity, consequential/punitive damages, a
"notwithstanding anything to the contrary" override). The drafter fixed every one in a single
pass, and the independent verifier returned `passed: true` with no unmet items — so the loop
exited on **iteration 1**. None of the three hard stops were tested.

That's the honest, useful outcome: when one pass is enough, a goal loop just runs once — but
the verifier still earns its place, because a `passed` you can't independently check is just
the drafter agreeing with itself. The loop's payoff shows up when the first draft *misses*; to
see the feedback cycle actually turn, run the experiments below (weaken the drafter, add a
criterion mid-run, tighten the budget). Full write-up: [`../logs/07-goal-loop.md`](../logs/07-goal-loop.md).

## Try it yourself

Ask Claude: **"run recipe 07 from the cookbook."** Experiments:
- Add a 5th criterion mid-way and watch the verifier reopen the loop.
- Make the drafter weaker (tell it to "make minimal edits") and watch no-progress detection fire.
- Run it with a tight token target ("+80k, run recipe 07") and watch the budget ceiling stop it.

## Cost note

2 agents per iteration (drafter + verifier), sequential. Cost is bounded by `MAX_ITERS` × 2
agents — that cap *is* your budget. Cheap here (one short clause); scale the cap, not the
input, when a real task needs more rounds.
