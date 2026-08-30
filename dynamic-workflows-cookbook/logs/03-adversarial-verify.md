# Run log — Recipe 03 (Adversarial verify)

- **Run ID:** wf_2751062a-ae1
- **Pattern:** adversarial verify (parallel skeptics, majority vote)
- **Agents:** 6 (2 findings × 3 skeptics)
- **Duration:** 16,238 ms (~16s)
- **Tool uses:** 12
- **Subagent tokens:** ~122k
- **Outcome:** true finding survived (0/3 refuted); planted false finding dropped (3/3 refuted).

## Result

```json
{
  "survivors": ["termination-high"],
  "killed": ["notices-high"],
  "verified": [
    {"id": "termination-high", "file": "05-termination.txt", "refutes": 0, "votes": 3, "survives": true},
    {"id": "notices-high",     "file": "04-notices.txt",     "refutes": 3, "votes": 3, "survives": false}
  ]
}
```

## What we watched

Six `verify:` agents lit up at once (`termination-high#1..3` and `notices-high#1..3`). The
planted false finding ("notices is dangerously one-sided") was refuted unanimously — the
verification pass caught the bad finding before it could leave the workflow.
