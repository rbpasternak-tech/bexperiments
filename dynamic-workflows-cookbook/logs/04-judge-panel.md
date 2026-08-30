# Run log — Recipe 04 (Judge panel)

- **Run ID:** wf_c197a259-28b
- **Pattern:** judge panel (divergent drafts → independent judges → synthesis)
- **Agents:** 7 (3 drafts + 3 judges + 1 synthesis)
- **Duration:** 78,951 ms (~79s)
- **Tool uses:** 10
- **Subagent tokens:** ~155k
- **Outcome:** unanimous 3–0 for Candidate B (balanced-market); synthesis grafted 5 elements from A.

## Vote tally

```
A (customer-protective): 0
B (balanced-market):     3   <- winner (unanimous)
C (minimal-change):      0
```

All three judges independently chose B as the only fully mutual, market-standard, enforceable
draft that both sides would sign.

## Synthesis graft note (verbatim)

> Kept Candidate B's mutual, four-part structure, cap, and balanced carve-outs as the
> backbone. From Candidate A: (1) death/personal-injury and payment-obligations exclusions;
> (2) "whether in contract, tort, or otherwise" language; (3) IP-infringement indemnity
> trigger, recast mutually; (4) "agreed allocation of risk / essential basis of the bargain"
> sentence; (5) "affiliates" added to indemnified parties. From Candidate C: nothing of
> substance (its conflation of indemnity with the cap was the defect judges flagged). Light
> independent polish on the settlement proviso and notice/materiality qualifier.

## What we watched

3 `draft:` agents (one per angle) ran at once, then 3 `judge#` agents, then a single
`synthesize`. The final clause ended up stronger than any individual candidate — the point of
the pattern.
