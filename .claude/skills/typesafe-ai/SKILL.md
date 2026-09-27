---
name: typesafe-ai
description: Classify, risk-rate, or yes/no-evaluate documents with TypeSafe's JEV model (api.typesafe.ai). Use when the user says "JEV", "TypeSafe", or asks to classify or risk-score documents such as contracts, employment agreements, or policies with JEV.
---

# TypeSafe JEV classification

JEV is TypeSafe's "System One" model. It answers named questions about a piece
of content and returns calibrated probabilities, not prose:

- `noul` — yes/no question or statement → probability of yes/true (0–1).
- `choice` — pick one of named options → choice, confidence, probabilities.
- `score` — ordered rubric (level 0, 1, 2, …) → expected score, confidence.

API reference: `https://api.typesafe.ai/docs` (OpenAPI at `/openapi.json`).
Models: `GET /v1/models` (`jev-latest`, `jev-preview`).

## Auth

- Claude Code cloud sessions: the agent proxy injects the TypeSafe key for
  `api.typesafe.ai`; send no header.
- Local: export `TYPESAFE_API_KEY`; the script sends it as `Bearer`.
  Never commit the key.

## Workflow

1. Pick or write a rubric in `rubrics/` (JSON with a `questions` object in
   TypeSafe's request format). Frame questions from the side the user is on
   (e.g. employer vs. employee, customer vs. vendor).
2. Run the classifier on the documents:

   ```bash
   python .claude/skills/typesafe-ai/scripts/jev_classify.py \
     --rubric .claude/skills/typesafe-ai/rubrics/employment-termination.json \
     --out <project>/work/jev_results.json \
     legal-test-docs/employment/*.md
   ```

3. Report a table: risk choice + confidence, score, and each yes/no
   probability. Flag any answer with confidence below ~0.5 for human review.
4. Read the documents yourself and explain *why* JEV rated each one as it
   did, citing the clauses. Call out where you disagree with JEV.
5. Add a caveat that the output is not legal advice.

## Rubrics

- `employment-termination.json` — employer-side exposure to
  wrongful-termination / fired-without-proper-warning claims: HIGH/MEDIUM/LOW
  risk, 0–4 severity, and yes/no checks for at-will protection, promised
  warning process, policy deviation, and retaliation signals.

## Notes

- Only send documents the user has asked to classify; content leaves the
  machine to TypeSafe.
- Answers are keyed by the question names in the rubric; the response
  `model` field shows the resolved version (e.g. `jev-1.13.0`).
