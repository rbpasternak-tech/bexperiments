# Recipe 01 — Fan-out

## What you'll learn

The most basic dynamic-workflow move: doing many independent tasks **at the same time**
instead of one after another.

## The pattern in one sentence

One task → split into N independent pieces → run an agent on every piece concurrently →
collect the results.

## When to reach for it (and when not to)

**Reach for it when** the pieces of work don't depend on each other: reviewing 20 files,
classifying 50 records, summarizing 10 documents. None of them needs another's answer first,
so there's no reason to make them wait in line.

**Don't reach for it when** the steps depend on each other (step 2 needs step 1's output —
that's a *pipeline*, recipe 02), or when there's only one piece of work (a single agent is
simpler and cheaper). Fan-out buys you **speed**, nothing more. If the work is already fast,
you don't need it.

## The script (annotated)

See [`01-fan-out.workflow.js`](01-fan-out.workflow.js). The whole pattern is one call:

```js
const results = await parallel(CLAUSES.map(name => () =>
  agent(`Read ${DIR}/${name} ... classify its risk ...`, { schema: SCHEMA })
))
```

Three things worth understanding:

- **`parallel([...thunks])`** runs all the functions concurrently. We pass *functions*
  (`() => agent(...)`), not already-running calls, so `parallel` decides when each launches.
- **`schema: SCHEMA`** forces each agent to return clean structured data (`{file, title,
  risk, reason}`) instead of prose. No parsing on our side.
- **`parallel` is a barrier**: the line after it runs only once *all* agents finish. An
  agent that errors becomes `null`, so we `.filter(Boolean)` before using the results.

## What happened when we ran it

5 agents, all launched at once, finished in **13 seconds total**. Results:

| Clause | Risk | Reason (one line) |
|---|---|---|
| 01 Liability | **HIGH** | Customer liability uncapped, includes punitive damages, one-way indemnity |
| 02 Governing law | LOW | Standard mutual Delaware choice, applies equally to both parties |
| 03 Auto-renewal | **HIGH** | Auto-renews + Provider may raise fees any amount, immediately, no notice |
| 04 Notices | LOW | Standard mutual notices provision |
| 05 Termination | **HIGH** | Provider exits at will with no liability; customer can never exit |

It correctly flagged the 3 clauses we planted as one-sided and left the 2 standard ones LOW.

**The lesson in the numbers:** 5 clauses judged in 13s. One agent doing them in sequence
would take roughly 5× longer, because it can't begin clause 2 until clause 1 is done. The
clauses don't depend on each other, so we don't make them wait. That's the entire point.

## Try it yourself

Ask Claude: **"run recipe 01 from the cookbook."** While it runs, type `/workflows` to watch
the 5 `classify:` agents execute in parallel. To experiment: drop another `.txt` clause into
`corpus/clauses/`, add its filename to the `CLAUSES` list, and re-run — the fan-out widens
automatically.

## Cost note

~5 agents on ~1-paragraph inputs. About as cheap as a workflow gets. The cost scales with
the number of pieces: 5 clauses ≈ 5 agents; 500 clauses ≈ 500 agents (and ~100× the tokens),
though only ~10–16 actually run at any instant — the rest queue. Keep inputs small while
learning the shape; scale deliberately when a real task needs it.
