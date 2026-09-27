# Contract Risk Evaluator

A command-line tool that scores contracts on risk and compliance dimensions
using [TypeSafe](https://typesafe.ai)'s System One API (model `jev-latest`).

Each document goes to TypeSafe as one request. Every rubric dimension is a
typed question in that request, and each answer comes back as a probability,
a choice, or a position on a scale rather than as generated text. The CLI
turns each answer into a 0–100 risk value, prints a table per document and a
ranked summary, and writes a JSON report.

## Setup

```bash
cd contract-risk-evaluator
pip install -r requirements.txt       # only needed for .docx and .pdf inputs
export TYPESAFE_API_KEY=ts_...        # from your TypeSafe dashboard; never commit it
```

`TYPESAFE_API_BASE` optionally overrides `https://api.typesafe.ai`. Without
`TYPESAFE_API_KEY` the client sends no `Authorization` header, which suits
Claude Code cloud sessions whose egress proxy injects the key.

## Usage

```bash
python evaluate.py ../legal-test-docs                 # every .txt/.md/.docx/.pdf in a folder
python evaluate.py nda.docx msa.pdf --output outputs/review.json
python evaluate.py contracts/ --flag-threshold 0.5    # flag more aggressively
python evaluate.py contracts/ --rubric rubrics/my-rubric.json
python evaluate.py contracts/ --dry-run               # print the request; no API call
python selfcheck.py                                   # offline checks with a fake API
```

| Option | Default | Purpose |
| --- | --- | --- |
| `--rubric` | `rubrics/contract-risk.json` | Dimensions to evaluate |
| `--model` | `jev-latest` | TypeSafe model (`jev-preview` also exists) |
| `--output` | `outputs/risk-report-<timestamp>.json` | JSON report path |
| `--flag-threshold` | `0.6` | Risk at or above which a dimension gets `!` |
| `--max-chars` | no limit | Truncate long documents before sending |
| `--workers` | `4` | Documents evaluated in parallel |

The exit code is 0 on success, 1 if any document failed, and 2 for usage
errors such as a missing key.

## Default dimensions

| Dimension | Type | Risky answer |
| --- | --- | --- |
| Overall risk | score | Low → Moderate → High → Critical |
| Limitation of liability | choice | one-sided cap, uncapped, or missing |
| Indemnification | score | balanced → broad, one-sided, uncapped |
| Termination rights | choice | one-sided or missing |
| Auto-renewal trap | noul | yes |
| Unilateral changes | noul | yes |
| Data protection | choice | partial or absent |
| Confidentiality | score | robust → absent |
| IP overreach | noul | yes |
| Restrictive covenants | noul | yes |
| Governing law gap | noul | yes |
| Compliance red flags | noul | yes |

Risk is judged from the perspective of the party receiving the draft.

## How answers become risk

- **noul** (yes/no): the probability of "yes". Phrase every noul so that yes
  means risk.
- **score**: the weighted position on the scale divided by the top level.
  List criteria from least to most risky.
- **choice**: expected risk, which is the sum of each option's probability
  times the weight in the dimension's `risk` map.

A document's overall number is the mean of its dimension risks. The
confidence column is TypeSafe's confidence for choices and scores; for nouls
it is the distance of the probability from 0.5.

## Custom rubrics

Copy `rubrics/contract-risk.json` and edit the dimensions. Each entry needs
`id`, `label`, `type` (`noul`, `choice`, or `score`), `instructions`, and,
for choice and score, `criteria`. A choice also needs a `risk` weight from 0
to 1 for every option. The rubric is validated before any API call.

## Files

- `evaluate.py`: CLI entry point, table output, and JSON report
- `typesafe_client.py`: `POST /v1/systemone` client with retries and error parsing
- `rubric.py`: rubric validation, question building, and answer-to-risk mapping
- `document_loader.py`: text extraction for .txt, .md, .docx, and .pdf
- `selfcheck.py`: offline checks against a fake TypeSafe transport
- `outputs/`: reports, gitignored because they describe possibly confidential contracts

## Limits

- The whole document is one state. Jev 1.13 allows 32k tokens for the state
  plus the longest question (roughly 100k characters of contract text); a
  longer contract fails with the API error shown for that document, and
  `--max-chars` is the workaround. Accuracy also drops as irrelevant text
  grows, so clause-level evaluation is a likely next step.
- Jev reads questions literally; if a dimension misfires, tighten its
  instructions and criteria in the rubric rather than the code.
- Scanned PDFs with no text layer need OCR first.
- The scores are a triage signal, not legal advice.
