# Run log — Recipe 02 (Pipeline)

- **Run ID:** wf_e2fad84f-291
- **Pattern:** pipeline (`pipeline`) — analyze → draft fix, per clause
- **Agents:** 10 (5 analyze + 5 fix)
- **Duration:** 34,258 ms (~34s)
- **Tool uses:** 24
- **Subagent tokens:** ~212k
- **Outcome:** 3 fixes drafted (HIGH clauses), 2 passed through unchanged (LOW clauses).

## Summary of output

| Clause | Risk | changeNeeded | Fix summary |
|---|---|---|---|
| 01-liability | HIGH | yes | Mutual liability cap (trailing 12-mo fees) + carve-outs + two-way indemnity |
| 02-governing-law | LOW | no | no change needed |
| 03-auto-renewal | HIGH | yes | Price increase capped at max(CPI, 5%), 60-day notice, consent above cap |
| 04-notices | LOW | no | no change needed |
| 05-termination | HIGH | yes | Mutual termination + cure, pro-rata refunds, no acceleration, survival |

Full drafted redline text is in the raw task result; the recipe writeup quotes the highlights.

## What we watched

In the `/workflows` tree, `fix:` agents began appearing while some `analyze:` agents were
still running — the visual confirmation that there is no barrier between the two stages and
each clause advances on its own schedule.
