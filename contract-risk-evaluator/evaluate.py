#!/usr/bin/env python3
"""Evaluate contracts for risk and compliance with TypeSafe's System One API.

Each document is sent to TypeSafe once, with every rubric dimension as a
typed question. The CLI prints a per-document risk table and writes a JSON
report.

Usage:
    python evaluate.py contracts/                       # every supported file in a folder
    python evaluate.py nda.docx msa.pdf --output report.json
    python evaluate.py contracts/ --rubric rubrics/my-rubric.json
    python evaluate.py contracts/ --dry-run             # show the request, call nothing
"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from document_loader import collect_paths, load_text
from rubric import build_questions, interpret, load_rubric
from typesafe_client import DEFAULT_MODEL, TypeSafeClient, TypeSafeError

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RUBRIC = os.path.join(HERE, "rubrics", "contract-risk.json")
DEFAULT_OUTPUT_DIR = os.path.join(HERE, "outputs")


def parse_args(argv=None):
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Score contracts on risk and compliance dimensions using TypeSafe.")
    parser.add_argument("inputs", nargs="+", help="Files or folders (.txt, .md, .docx, .pdf)")
    parser.add_argument("--rubric", default=DEFAULT_RUBRIC, help="Rubric JSON (default: contract-risk)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"TypeSafe model (default: {DEFAULT_MODEL})")
    parser.add_argument("--output", help="JSON report path (default: outputs/risk-report-<timestamp>.json)")
    parser.add_argument("--flag-threshold", type=float, default=0.6,
                        help="Risk from 0 to 1 at or above which a dimension is flagged (default: 0.6)")
    parser.add_argument("--max-chars", type=int, default=0,
                        help="Truncate each document to this many characters (default: no limit)")
    parser.add_argument("--workers", type=int, default=4, help="Documents evaluated in parallel (default: 4)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the request for the first document and exit without calling the API")
    return parser.parse_args(argv)


def build_state(path, text):
    """Return the TypeSafe state for one document."""
    return {"document": os.path.basename(path), "contract_text": text}


def evaluate_document(client, rubric, questions, path, max_chars):
    """Evaluate one document and return its report entry.

    Args:
        client: A ``TypeSafeClient``.
        rubric: The loaded rubric.
        questions: The questions built from ``rubric``.
        path: Document path.
        max_chars: Truncation limit, or 0 for none.

    Returns:
        A dict with per-dimension results, or with ``error`` on failure.
    """
    entry = {"document": path}
    try:
        text = load_text(path)
        entry["characters"] = len(text)
        if max_chars and len(text) > max_chars:
            text = text[:max_chars]
            entry["truncated_to"] = max_chars
        result = client.evaluate(build_state(path, text), questions)
    except (OSError, ValueError, RuntimeError, TypeSafeError) as exc:
        entry["error"] = str(exc)
        return entry

    dimensions = []
    for dim in rubric["dimensions"]:
        raw = result["answers"][dim["id"]]
        dimensions.append({"id": dim["id"], "label": dim.get("label", dim["id"]),
                           **interpret(dim, raw), "raw": raw})
    entry.update({
        "model": result.get("model"),
        "usage": result["usage"],
        "overall_risk": sum(d["risk"] for d in dimensions) / len(dimensions),
        "dimensions": dimensions,
    })
    return entry


def risk_bar(risk, width=10):
    """Return a text bar for a risk from 0 to 1."""
    filled = round(max(0.0, min(1.0, risk)) * width)
    return "#" * filled + "." * (width - filled)


def truncate(text, width):
    """Shorten ``text`` to ``width`` characters with an ellipsis."""
    return text if len(text) <= width else text[:width - 1] + "…"


def print_report(entries, threshold):
    """Print per-document tables and a summary."""
    for entry in entries:
        print(f"\n{entry['document']}")
        if "error" in entry:
            print(f"  ERROR: {entry['error']}")
            continue
        note = f", truncated to {entry['truncated_to']:,}" if "truncated_to" in entry else ""
        print(f"  {entry['characters']:,} chars{note} · model {entry['model']} · "
              f"{entry['usage'].get('input_tokens', '?')} input tokens")
        print(f"  {'Dimension':<24} {'Answer':<44} {'Risk':>4} {'':10} {'Conf':>4}")
        print(f"  {'-' * 24} {'-' * 44} {'-' * 4} {'-' * 10} {'-' * 4}")
        for dim in entry["dimensions"]:
            flag = " !" if dim["risk"] >= threshold else ""
            print(f"  {truncate(dim['label'], 24):<24} {truncate(dim['answer'], 44):<44} "
                  f"{round(dim['risk'] * 100):>4} {risk_bar(dim['risk'])} "
                  f"{round(dim['confidence'] * 100):>4}{flag}")

    scored = [e for e in entries if "error" not in e]
    print("\nSummary (risk 0-100, ! = at or above flag threshold)")
    print(f"  {'Document':<40} {'Risk':>4}  Flagged dimensions")
    for entry in sorted(scored, key=lambda e: e["overall_risk"], reverse=True):
        flagged = [d["label"] for d in entry["dimensions"] if d["risk"] >= threshold]
        print(f"  {truncate(os.path.basename(entry['document']), 40):<40} "
              f"{round(entry['overall_risk'] * 100):>4}  {', '.join(flagged) or '-'}")
    failed = len(entries) - len(scored)
    if failed:
        print(f"  {failed} document(s) failed; see errors above.")


def main(argv=None, client=None):
    """Run the CLI.

    Args:
        argv: Arguments, defaulting to ``sys.argv[1:]``.
        client: Optional client override, used by the self-check.

    Returns:
        0 on success, 1 if any document failed, 2 on usage errors.
    """
    args = parse_args(argv)
    try:
        rubric = load_rubric(args.rubric)
        paths = collect_paths(args.inputs)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not paths:
        print("error: no .txt, .md, .docx, or .pdf files found", file=sys.stderr)
        return 2
    questions = build_questions(rubric)

    if args.dry_run:
        text = load_text(paths[0])
        if args.max_chars:
            text = text[:args.max_chars]
        state = build_state(paths[0], text)
        state["contract_text"] = truncate(state["contract_text"], 500)
        print(json.dumps({"model": args.model, "state": state, "questions": questions}, indent=2))
        print(f"\n(dry run: {len(paths)} document(s), {len(questions)} questions each; "
              "contract_text shortened for display)", file=sys.stderr)
        return 0

    client = client or TypeSafeClient(model=args.model)
    if not client.api_key:
        print("note: TYPESAFE_API_KEY is not set; relying on a proxy to authenticate",
              file=sys.stderr)

    print(f"Evaluating {len(paths)} document(s) on {len(questions)} dimensions with {args.model}…",
          file=sys.stderr)
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        entries = list(pool.map(
            lambda p: evaluate_document(client, rubric, questions, p, args.max_chars), paths))

    print_report(entries, args.flag_threshold)

    output = args.output or os.path.join(
        DEFAULT_OUTPUT_DIR, f"risk-report-{datetime.now():%Y%m%d-%H%M%S}.json")
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rubric": rubric.get("name", os.path.basename(args.rubric)),
        "model_requested": args.model,
        "flag_threshold": args.flag_threshold,
        "documents": entries,
    }
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    print(f"\nJSON report: {output}")
    return 1 if any("error" in e for e in entries) else 0


if __name__ == "__main__":
    sys.exit(main())
