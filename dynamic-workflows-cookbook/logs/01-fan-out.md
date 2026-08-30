# Run log — Recipe 01 (Fan-out)

- **Run ID:** wf_341f03a9-430
- **Pattern:** fan-out (`parallel`)
- **Agents:** 5 (one per clause)
- **Duration:** 13,077 ms (~13s)
- **Tool uses:** 10 (each agent: Read + StructuredOutput)
- **Subagent tokens:** ~104k
- **Outcome:** 3 HIGH / 2 LOW — correctly flagged all 3 planted one-sided clauses.

## Raw result

```json
{
  "highRiskCount": 3,
  "results": [
    {"file": "01-liability.txt",     "risk": "HIGH", "title": "Unlimited Customer Liability & One-Sided Indemnity"},
    {"file": "02-governing-law.txt", "risk": "LOW",  "title": "Governing Law & Exclusive Delaware Jurisdiction"},
    {"file": "03-auto-renewal.txt",  "risk": "HIGH", "title": "Auto-Renewal with Uncapped Discretionary Price Increases"},
    {"file": "04-notices.txt",       "risk": "LOW",  "title": "Notices"},
    {"file": "05-termination.txt",   "risk": "HIGH", "title": "Unilateral Provider Termination, No Customer Exit"}
  ]
}
```

## What we watched

All 5 `classify:` agents lit up in the `/workflows` progress tree at once and finished
within a couple seconds of each other — the visual proof that the work happened in parallel,
not in sequence.
