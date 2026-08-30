# Run log — Recipe 05 (Loop-until-dry)

- **Run ID:** wf_3e866877-e8b
- **Pattern:** loop-until-dry (sequential finder rounds, stop on 2 dry rounds or cap)
- **Agents:** 5 (one per round)
- **Duration:** 222,218 ms (~3.7 min) — slowest recipe; sequential by nature
- **Tool uses:** 30
- **Subagent tokens:** ~123k
- **Outcome:** **hit the 5-round safety cap (`hitCap: true`) — never went dry.** 23 distinct
  issues found, still discovering new ones at round 5.

## Trajectory

| Round | Behavior |
|---|---|
| 1 | Obvious issues (unlimited liability, at-will termination, uncapped fee hikes) |
| 2–4 | Progressively subtler issues; counter kept resetting (kept finding new) |
| 5 | Still finding new issues (certified-mail deadline trap, first-party indemnity sweep) → hit cap |

The dryness counter never reached 2 — the run was stopped by `MAX_ROUNDS`, not by exhaustion.
The workflow logged "Stopped at safety cap … may not be fully drained" rather than implying
completeness.

## Sample of the 23 issues (depth increases over rounds)

- [01-liability] Liability is "unlimited," "without cap and without regard to fault."
- [05-termination] Provider may terminate "for any reason or no reason," no liability.
- [03-auto-renewal] Fees may rise "any amount … effective immediately, without prior notice."
- [01-liability] "Notwithstanding anything to the contrary" overrides every other clause.
- [01-liability] Indemnity sweeps in first-party losses → backdoor uncapped direct-damages.
- [04-notices] Certified mail deemed-given rule silently shortens the 90-day non-renewal window.
- [05-termination] Silent on data return → no contractual right to retrieve own data on exit.

(Full 23 in the raw task result.)
