# Recipe 05 — Loop-until-dry

## What you'll learn

How to handle discovery when you *don't know how much there is to find* — so you don't
stop too early (miss the tail) or waste rounds searching after you're done.

## The pattern in one sentence

Keep spawning finders — each told what's already been found — until K rounds in a row turn
up nothing new (and always cap the rounds as a backstop).

## When to reach for it (and when not to)

**Reach for it when** the size of the result set is unknown: "find *all* the bugs," "list
*every* problematic clause," "what edge cases exist?" A single pass under-finds; a fixed
number of passes is a guess.

**Don't reach for it when** you already know the work-list (just fan out — recipe 01) or
when one pass is genuinely enough. This pattern trades more agents for more completeness —
spend it when *missing something* is the risk.

## Why fan-out can't do this

Fan-out (01) and pipeline (02) assume you can **enumerate the work up front** — 5 files, 3
candidates. Loop-until-dry is for when you *can't*: you don't know if there are 3 problems
or 30, so you keep going until the finders stop surfacing anything new.

## The mechanics that make it work

1. **Carry state across rounds.** Each round gets the list of issues already found and is
   told to return *only new ones*. Without that, every round just re-finds the obvious stuff.
2. **A dryness counter, not a fixed count.** Stop after K consecutive empty rounds (here
   K=2) — that's the signal you've drained the well, adaptive to however much was there.
3. **Always a safety cap.** A `MAX_ROUNDS` backstop so a stubborn search can't loop forever
   — and **if you hit the cap, log that you may not be fully drained** (see what happened
   below — this is not hypothetical).

## The script (annotated)

See [`05-loop-until-dry.workflow.js`](05-loop-until-dry.workflow.js). The shape is a `while`
loop, not a `parallel`:

```js
while (dry < 2 && round < MAX_ROUNDS) {
  const exclude = allIssues.map(i => `[${i.clause}] ${i.issue}`).join('\n')  // what's known
  const res = await agent(`...find issues NOT already in:\n${exclude}...`, { schema })
  const fresh = res.issues.filter(notSeenBefore)
  if (fresh.length === 0) dry++          // a dry round
  else { dry = 0; allIssues.push(...fresh) }  // found new -> reset the counter
}
```

Note it's **sequential** — each round needs the previous round's findings to know what to
exclude. That's the one cookbook pattern that *can't* be parallelized within itself.

## What happened when we ran it

5 rounds, ~3.7 minutes, 5 agents. And the honest, instructive result: **it hit the 5-round
safety cap while still finding new issues — it never went dry.** From 5 short clauses it
surfaced **23 distinct problems**, getting *deeper* each round:

- **Round 1** — the obvious: "liability is unlimited," "provider can terminate at will."
- **Later rounds** — subtle traps a single pass would never reach:
  - *"Using certified mail silently shortens your 90-day non-renewal deadline by 3 business
    days — a hidden way to get auto-renewed."*
  - *"The indemnity sweeps in first-party losses, turning it into a backdoor uncapped
    direct-damages claim."*
  - *"'Notwithstanding anything to the contrary' makes this one-sided regime override every
    other clause in the agreement."*

**The lesson in the result:** loop-until-dry finds *depth* a single pass can't — 23 issues
vs. the ~5 a fan-out would surface. And the cap-hit is the teaching moment: the counter said
"still finding things," the cap said "stop." When you hit the cap, you haven't necessarily
finished — you've hit your budget. Raise `MAX_ROUNDS` to keep digging, or accept the cap as
your cost ceiling. **The workflow logged exactly this** ("may not be fully drained") instead
of pretending it was done — never let a capped search masquerade as a complete one.

## Try it yourself

Ask Claude: **"run recipe 05 from the cookbook."** Experiment: raise `MAX_ROUNDS` to 8 and
see if it eventually goes dry; or lower the dry threshold to 1 and watch it stop sooner.

## Cost note

~1 agent per round (5 here). Cost is unbounded in principle — that's why the cap exists.
Sequential, so it's also the *slowest* pattern per result. Use it when completeness matters
more than speed; set the cap to your real budget.
