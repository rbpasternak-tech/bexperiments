# Recipe 03 — Adversarial verify

## What you'll learn

How a dynamic workflow buys **confidence** instead of speed: catching plausible-but-wrong
answers a single agent would hand you with a straight face.

## The pattern in one sentence

For each finding, spawn several **independent skeptics** whose job is to *refute* it, and keep
the finding only if it survives a majority.

## When to reach for it (and when not to)

**Reach for it when** being *wrong* is expensive and findings can be plausibly false: legal
risk flags, security vulnerabilities, "this code has a bug" claims, factual assertions in a
report. Anywhere a confident-sounding wrong answer would do damage.

**Don't reach for it when** the answer is trivially checkable, low-stakes, or there's nothing
to be wrong about. Verification multiplies cost (N skeptics per finding) — spend it where a
false positive actually hurts.

## Why this is different from fan-out and pipeline

Recipes 01 and 02 made you **faster**. This one makes you **right**. It's a quality filter,
not a throughput tool. Same machinery (parallel agents), completely different purpose.

## The three things that make it work

1. **Independence** — skeptics don't see each other's votes, so they can't herd toward a
   wrong consensus. Each judges the raw clause fresh.
2. **Framing as refute** — the job is "try to *break* this," not "evaluate this." Actively
   hunting for the flaw surfaces weaknesses that a neutral "looks fine to me" pass misses.
3. **A majority threshold** — one skeptic can be wrong; a majority agreeing is the signal.
   Here, 3 skeptics, survive only if fewer than 2 refute.

## The script (annotated)

See [`03-adversarial-verify.workflow.js`](03-adversarial-verify.workflow.js). It's parallel
nested in parallel — for each finding, three skeptics at once:

```js
const verified = await parallel(FINDINGS.map(f => () =>
  parallel([1,2,3].map(i => () =>
    agent(`Read ${f.file}. Claim: "${f.claim}". REFUTE it if you can.`, { schema: VOTE_SCHEMA })
  )).then(votes => {
    const refutes = votes.filter(v => v.refuted).length
    return { ...f, survives: refutes < 2 }   // majority of 3 = 2
  })
))
```

The `.then(...)` after the inner `parallel` is the tally step: count the refute votes and
decide if the finding lives.

## What happened when we ran it

6 skeptics (3 per finding), **16 seconds**. We fed it one true finding and one deliberately
planted false one:

| Finding | Skeptics refuting | Verdict |
|---|---|---|
| Termination is HIGH risk *(true)* | **0 of 3** | survives ✅ |
| Notices is HIGH risk *(planted false)* | **3 of 3** | refuted & dropped ❌ |

The true finding held up — nobody could honestly knock it down. The false finding was caught
unanimously: all three skeptics read the actual notices clause, saw it's a standard *mutual*
provision, and refuted the "dangerously one-sided" claim. **The bad finding never escaped the
workflow** — exactly what you want a verification pass to do.

## Try it yourself

Ask Claude: **"run recipe 03 from the cookbook."** To really see it work, edit `FINDINGS` to
add your own borderline or wrong claim and watch whether the skeptics catch it. Try changing
the threshold (`refutes < 2`) to see how strict/lenient verification gets.

## Cost note

~6 agents here (2 findings × 3 skeptics). Cost = findings × skeptics. More skeptics = more
confidence but more tokens; 3 is a sensible default. Only verify the findings that matter —
don't run 3 skeptics on a hundred trivial results.
