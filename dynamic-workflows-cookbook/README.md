# Dynamic Workflows Cookbook

A hands-on, learn-by-watching guide to **dynamic workflows** in Claude Code — the
Opus 4.8 capability that turns a single task into many self-coordinating agents that
fan out, run in parallel, verify each other, and loop.

This cookbook isn't written from theory. Each recipe was **run live and watched**, then
captured: you get the exact script, a plain-language explanation of the pattern, and a
log of what actually happened when we ran it.

## Start here

- **[CONCEPTS.md](CONCEPTS.md)** — the mental model. Read this first. What a dynamic
  workflow *is*, the handful of patterns, how to think about cost, and when *not* to use one.

## The recipes (simplest → most sophisticated)

Each lesson builds on the last. Do them in order; stop anytime.

| #  | Pattern | One-line idea | Status |
|----|---------|---------------|--------|
| 01 | [Fan-out](recipes/01-fan-out.md) | One task → N agents at once → collect results | ✅ captured (5 agents, 13s) |
| 02 | [Pipeline](recipes/02-pipeline.md) | Each item flows through stages independently, no waiting | ✅ captured (10 agents, 34s) |
| 03 | [Adversarial verify](recipes/03-adversarial-verify.md) | Spawn skeptics to refute a finding before trusting it | ✅ captured (6 agents, 16s) |
| 04 | [Judge panel](recipes/04-judge-panel.md) | N independent attempts → score → synthesize the winner | ✅ captured (7 agents, 79s) |
| 05 | [Loop-until-dry](recipes/05-loop-until-dry.md) | Keep searching until rounds stop finding anything new | ✅ captured (5 rounds, 23 issues) |
| 06 | [Sweep + critic](recipes/06-sweep-and-critic.md) | Search many ways, then ask "what did we miss?" | ✅ captured (4 agents, +8 missed) |
| 07 | [Goal loop](recipes/07-goal-loop.md) | Draft → verify → feed failures back → repeat until it passes | ✅ captured (2 agents, passed iter 1) |

## How to run a recipe yourself

The scripts in `recipes/*.workflow.js` run via Claude Code's **`Workflow` tool**, not as
standalone Node. The simplest way: ask Claude "run recipe 01 from the cookbook." See
[CONCEPTS.md → How you actually run these](CONCEPTS.md#how-you-actually-run-these).

## What's in here

```
README.md       you are here — the map + recipe index
CONCEPTS.md     the mental model (read first)
recipes/        one .md (explanation) + one .workflow.js (script) per pattern
corpus/         tiny invented sample data the recipes run against (no real data)
logs/           a short log of what happened each time we ran a recipe live
```
