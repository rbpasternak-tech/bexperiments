"""Classify documents with TypeSafe's JEV model using a JSON rubric.

Sends each document to POST /v1/systemone on api.typesafe.ai with the
rubric's named questions, prints a one-line summary per document, and
writes the full responses to a JSON file.

Usage:
    python jev_classify.py --rubric ../rubrics/employment-termination.json \
        --out results.json path/to/doc1.md path/to/doc2.md
"""

import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

API_URL = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"


def classify(path, questions, model):
    """Send one document to JEV and return the parsed response.

    Args:
        path: pathlib.Path of the text document to classify.
        questions: dict of named TypeSafe questions (noul, choice, score).
        model: TypeSafe model name or alias, e.g. "jev-latest".

    Returns:
        dict: the SystemOneResponse (model, answers, usage).

    Raises:
        urllib.error.HTTPError: if the API rejects the request.
    """
    body = json.dumps({
        "model": model,
        "state": {"document": path.name, "text": path.read_text()},
        "questions": questions,
    }).encode()
    headers = {"Content-Type": "application/json"}
    # Cloud sessions get the key injected by the proxy; locally, set TYPESAFE_API_KEY.
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(API_URL, data=body, headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def summarize(answer):
    """Render one answer as a compact string.

    Args:
        answer: a TypeSafe answer dict (type noul, choice, or score).

    Returns:
        str: e.g. "HIGH (0.97)", "3.39 (0.80)", or "0.94".
    """
    if answer["type"] == "choice":
        return f"{answer['choice']} ({answer['confidence']:.2f})"
    if answer["type"] == "score":
        return f"{answer['score']:.2f} ({answer['confidence']:.2f})"
    return f"{answer['noul']:.2f}"


def main():
    """Parse arguments, classify every document, and write results.

    Returns:
        int: process exit code (0 on success, 1 if any document failed).
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="+", type=pathlib.Path)
    parser.add_argument("--rubric", required=True, type=pathlib.Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path("jev_results.json"))
    args = parser.parse_args()

    questions = json.loads(args.rubric.read_text())["questions"]
    results, failed = {}, False
    for path in args.files:
        try:
            result = classify(path, questions, args.model)
        except urllib.error.HTTPError as error:
            print(f"{path.name}: HTTP {error.code} {error.read().decode()[:300]}", file=sys.stderr)
            failed = True
            continue
        results[str(path)] = result
        parts = [f"{name}={summarize(a)}" for name, a in result["answers"].items()]
        print(f"{path.name}  [{result['model']}]  " + "  ".join(parts))

    args.out.write_text(json.dumps(results, indent=1))
    print(f"Wrote {len(results)} result(s) to {args.out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
