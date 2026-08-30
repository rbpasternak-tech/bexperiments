# Run log — Recipe 07 (Goal loop / loop engineering)

- **Run ID:** wf_59f97408-667
- **Pattern:** goal loop — draft → independent verifier (can say *no*) → feed failures forward → repeat until sign-off or a guard fires
- **Agents:** 2 (1 drafter + 1 verifier) — the loop ran a single iteration
- **Duration:** 24,243 ms (~24s)
- **Tool uses:** 3
- **Subagent tokens:** ~43k
- **Outcome:** `passed` on **iteration 1** — the verifier signed off on the first draft; `remainingFailures: []`

## What happened

The target was `corpus/clauses/01-liability.txt`, a clause that violated **all four**
acceptance criteria at once: unlimited customer liability, a one-sided customer-only
indemnity, consequential + punitive damages swept in, and a "notwithstanding anything to the
contrary" override.

Round 1, the drafter fixed every criterion in one pass. Its own one-line note:

> Capped each party's liability to trailing 12 months' fees, excluded consequential/punitive
> damages, made indemnity mutual and breach-based, and removed the "notwithstanding anything
> to the contrary" override.

The independent verifier checked it against all four criteria and returned `passed: true`
with no unmet items, so the loop exited immediately. No second draft was needed.

## The clause it converged on

> LIMITATION OF LIABILITY. Subject to the other terms of this Agreement, each party's
> aggregate liability under or relating to this Agreement shall not exceed the total fees paid
> or payable by Customer under this Agreement during the twelve (12) months immediately
> preceding the event giving rise to the claim. Neither party shall be liable to the other for
> any consequential, incidental, indirect, special, exemplary, or punitive damages, or for any
> lost profits, revenue, or data, regardless of the theory of liability and even if advised of
> the possibility of such damages. Each party (as the "Indemnifying Party") shall indemnify,
> defend, and hold harmless the other party from and against third-party claims to the extent
> arising out of the Indemnifying Party's breach of this Agreement, gross negligence, or
> willful misconduct, subject to the indemnified party providing prompt notice, reasonable
> cooperation, and sole control of the defense to the Indemnifying Party. The limitations and
> exclusions in this Section apply to the maximum extent permitted by applicable law and shall
> not limit a party's indemnification obligations under this Section or either party's
> liability for its breach of confidentiality obligations.

## The honest lesson: one-iteration convergence

This recipe *passed on the first try* — which is exactly the case the recipe text warns about:
when one pass is genuinely enough, you don't need a loop, you just need to ask once. So did the
loop earn its keep here? Two things to notice:

1. **The machinery still ran and still mattered.** The verifier is what *proved* the draft was
   done. Without an independent gate that can say no, a `passed` on iteration 1 is just the
   drafter agreeing with itself — you'd have no way to know whether it actually cleared all
   four criteria or only thought it did. The loop's value isn't only the re-drafting; it's the
   checkable sign-off.

2. **The loop shows its worth when the first draft *misses*.** With a strong model on one short
   clause, convergence is immediate. To actually watch the feedback cycle turn (and the
   no-progress guard fire), use the experiments in the recipe: weaken the drafter ("make
   minimal edits"), add a 5th criterion mid-run, or tighten the token budget. The point of the
   pattern is that you don't have to *know* whether one pass will be enough — the loop converges
   either way, in one round or six.

None of the three hard stops (iteration cap, no-progress detection, budget ceiling) fired —
the goal was met before any guard was tested.
