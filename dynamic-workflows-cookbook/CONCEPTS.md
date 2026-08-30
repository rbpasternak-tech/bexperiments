# Concepts: how to think about dynamic workflows

Read this once before the recipes. It's the map; the recipes are the territory.

## What is a dynamic workflow?

A normal Claude conversation is **one agent doing one thing at a time** — it reads, thinks,
acts, reads, thinks, acts, in a single line. That's perfect for most work.

A **dynamic workflow** is when a single task is broken into **many agents that run at the
same time** and coordinate. Instead of one worker reading 20 files one after another, you
spin up 20 workers who each read one file simultaneously and report back. "Dynamic" because
the *script* decides — with loops and conditionals — how many agents to spawn and what they
do, based on what it finds as it goes.

The slogan from the tweet that started this project: *"turns a single task into hundreds of
self-coordinating agents."* That's the idea. You rarely need hundreds — but the same
machinery that runs 5 runs 500.

## Why bother? Two reasons, and only two.

1. **Speed / scale** — work that doesn't depend on itself can happen at once. 20 files in
   the time of 1. This is *fan-out*.
2. **Confidence** — independent agents checking the same thing catch what one would miss.
   A finding that survives three skeptics is more trustworthy than one agent's say-so. This
   is *adversarial verify* and *judge panels*.

If a task needs neither speed nor confidence beyond what one agent gives you, **don't use a
workflow.** A single agent is simpler, cheaper, and easier to follow. Reaching for a
workflow when you don't need one is the most common beginner mistake.

## Subagent vs. dynamic workflow vs. managed agents

These three get talked about as if they're the same thing. They are not. They actually nest:

```
subagent          = one worker you delegate a chunk of work to
       | orchestrated by
dynamic workflow  = a script that coordinates MANY subagents (fan out, pipeline, loop)
       | a totally different paradigm from
managed agents    = a system YOU build and run yourself on the Anthropic API
```

A dynamic workflow is *made of* subagents. Managed agents are off to the side — a different,
much heavier way of building things.

| | **Subagent** | **Dynamic workflow** | **Managed agents** |
|---|---|---|---|
| What it is | One delegated helper | A script orchestrating many helpers | An app you build on the API |
| Who controls the steps | The model decides, in the moment | *Code* decides — loops, conditions, fan-out | *You* write the orchestration logic |
| Where it runs | Inside Claude Code | Inside Claude Code | Your own server |
| How much you build | Nothing — just ask | A short script | A server, agent defs, tool wiring, deploy |

**An analogy.** A *subagent* is asking one colleague "go check this and come back." A
*dynamic workflow* is handing the office a playbook — "send these 5 out at once, then have a
reviewer check each one" — where the office already has the staff and the building. *Managed
agents* is building and running your own office building: hiring the staff, defining every
role, installing the phones, keeping the lights on, whether or not you're there.

**Why this matters.** Managed agents is the heaviest of the three — you stand up the whole
orchestration system (server, agent definitions, tool wiring, deployment). Dynamic workflows
give you most of what that's reaching for — fan out across documents, analyze, draft, QA —
with **none** of the building. No server, no deploy. You write a short recipe and Claude Code
provides the whole factory. That's the lighter path: you rent the orchestration instead of
constructing it.

## Who decides this happens — you or Claude?

Two separate questions: who *builds* the workflow, and who *decides it runs*.

**Who builds it:** Claude does. You never write JavaScript. You state the *goal* ("classify
these clauses", "review these 20 files") and Claude translates it into the script. You decide
*what*; Claude handles *how*.

**Who decides it runs:** depends on scale.

| Scale | Who decides | Visible? |
|---|---|---|
| One subagent (or a few) | Claude decides automatically, as part of working | Yes — a tool call shows; you can always say "don't" |
| A dynamic workflow (many agents) | **You** — opt-in only | Always — Claude never launches one silently |

A single subagent is cheap, so Claude will delegate one on its own initiative (e.g. sending a
helper to search the codebase) — you see the result more than the decision. A dynamic workflow
spends real tokens across many agents, so the rule is firm: **it only runs when you ask for
it** (or invoke a skill/command that does). Claude will not spin up a fleet behind your back.

Note: "subagent" and "parallel agent" are the same building block — a *subagent* is one
delegated worker; "parallel" just means several of them running at once.

## The handful of patterns

You only need a few shapes. Everything else is a combination of these.

- **Fan-out** — N independent tasks, all at once, collect the results. (Recipe 01)
- **Pipeline** — each item flows through several stages (analyze → fix → check), and items
  move independently so a fast one isn't held back by a slow one. (Recipe 02)
- **Adversarial verify** — for each finding, spawn skeptics whose job is to *refute* it;
  keep only what survives. Buys confidence. (Recipe 03)
- **Judge panel** — generate several independent attempts from different angles, score them,
  keep the best (and graft good bits from the rest). Buys quality on open-ended problems.
  (Recipe 04)
- **Loop-until-dry** — when you don't know how much there is to find, keep spawning finders
  until a couple of rounds turn up nothing new. (Recipe 05)
- **Sweep + critic** — search several *different ways* (each blind to the others), then a
  final agent asks "what did we miss?" Buys coverage. (Recipe 06)
- **Goal loop** — draft, have an independent verifier check it against a checkable goal, feed
  the failures back, and repeat until it passes (or a guard fires). The "write loops, not
  prompts" pattern: you engineer the loop, not the prompt. (Recipe 07)

## The cost intuition (so this never feels scary)

Every agent you spawn costs tokens. Ten agents is roughly ten times one agent. That's the
trade: you spend tokens to buy time or confidence. Two simple habits keep it sane:

- **Keep inputs small.** A workflow over 5 short files is cheap. The same shape over 500
  long files is not — scale up deliberately, not by accident.
- **Match the fleet to the need.** "Find any obvious bugs" → a few agents. "Exhaustively
  audit this" → many agents + verification passes. Don't bring 50 agents to a 3-agent job.

Every recipe in this cookbook is intentionally tiny (≈3–6 agents, short inputs) so each one
is fast and cheap to watch. You learn the *shape*; you scale it when a real task needs it.

## How you actually run these

The `recipes/*.workflow.js` files are **not** standalone Node scripts. They use a special
vocabulary — `agent()`, `parallel()`, `pipeline()` — that only exists inside Claude Code's
**`Workflow` tool**. Three ways to run one:

1. **Ask Claude** (easiest): "run recipe 01 from the cookbook." Claude invokes the Workflow
   tool with that script.
2. **Watch it live**: while one runs, type `/workflows` to see the agents executing in
   real time — the progress tree, which agents are running, which finished.
3. **Save as a named workflow** (optional, later): copy a recipe into `.claude/workflows/`
   and it becomes invocable by name.

You never run these with `node`. If you try, they'll error — `agent()` isn't defined outside
the harness. That's expected.

## How to read a recipe

Each `recipes/NN-*.md` follows the same shape:

- **What you'll learn** — the one concept this recipe teaches.
- **The pattern in one sentence** — the shape, distilled.
- **When to reach for it (and when not to)** — the judgment call.
- **The script (annotated)** — the actual code, explained line by line.
- **What happened when we ran it** — the real result we watched.
- **Try it yourself** — how to re-run it.
- **Cost note** — roughly how many agents / how expensive.
