#!/usr/bin/env python3
"""Offline self-check for the contract risk evaluator (no pytest, no network).

The TypeSafe API is replaced by a fake transport whose responses follow the
shapes TypeSafe returns (see typesafe_client.py). Runs the rubric, the
loaders against ../legal-test-docs, the error handling, and a full CLI run.

Usage:
    python3 selfcheck.py          # prints PASS/FAIL per check, exits 1 on failure
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

import evaluate  # noqa: E402
import typesafe_client  # noqa: E402
from document_loader import collect_paths, load_text  # noqa: E402
from rubric import build_questions, interpret, load_rubric  # noqa: E402
from typesafe_client import TypeSafeClient, TypeSafeError  # noqa: E402

FIXTURES = os.path.join(HERE, "..", "legal-test-docs")
CHECKS = []


def check(func):
    """Register a self-check function."""
    CHECKS.append(func)
    return func


def fake_answer(question):
    """Return a plausible TypeSafe answer for one question."""
    if question["type"] == "noul":
        return {"type": "noul", "noul": 0.8}
    if question["type"] == "choice":
        options = list(question["criteria"])
        probs = {opt: 0.0 for opt in options}
        probs[options[0]] = 0.25
        probs[options[-1]] = 0.75
        return {"type": "choice", "choice": options[-1], "confidence": 0.7, "probabilities": probs}
    levels = [str(i) for i in range(len(question["criteria"]))]
    return {"type": "score", "score": 1.5, "confidence": 0.9,
            "legend": dict(zip(levels, question["criteria"])),
            "probabilities": {lvl: 1 / len(levels) for lvl in levels}}


def fake_transport(calls, responses=None):
    """Build a transport that records calls and replays or synthesizes responses."""
    queue = list(responses or [])

    def transport(url, headers, payload, timeout):
        calls.append({"url": url, "headers": headers, "payload": payload})
        if queue:
            return queue.pop(0)
        answers = {qid: fake_answer(q) for qid, q in payload["questions"].items()}
        return 200, json.dumps({"model": "jev-1.13.0", "answers": answers,
                                "usage": {"input_tokens": 500, "output_tokens": 60}})
    return transport


def make_client(calls, responses=None):
    """Return a client wired to the fake transport."""
    return TypeSafeClient(api_key="test-key", transport=fake_transport(calls, responses), max_retries=2)


@check
def default_rubric_is_valid():
    """The bundled rubric loads and yields one question per dimension."""
    rubric = load_rubric(evaluate.DEFAULT_RUBRIC)
    questions = build_questions(rubric)
    assert len(questions) == len(rubric["dimensions"]) >= 10
    assert {q["type"] for q in questions.values()} == {"noul", "choice", "score"}


@check
def rubric_rejects_missing_choice_risk():
    """A choice dimension without risk weights for every option is rejected."""
    bad = {"dimensions": [{"id": "x", "type": "choice", "instructions": "q",
                           "criteria": {"a": None, "b": None}, "risk": {"a": 0}}]}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(bad, handle)
    try:
        load_rubric(handle.name)
    except ValueError as exc:
        assert "risk" in str(exc)
    else:
        raise AssertionError("expected ValueError")
    finally:
        os.unlink(handle.name)


@check
def interpret_maps_answers_to_risk():
    """Noul, score, and choice answers map to the documented risk values."""
    noul = interpret({"id": "n", "type": "noul"}, {"type": "noul", "noul": 0.95})
    assert abs(noul["risk"] - 0.95) < 1e-9 and noul["answer"].startswith("yes")
    score_dim = {"id": "s", "type": "score", "criteria": ["Calm", "Frustrated", "Very angry"]}
    score = interpret(score_dim, {"type": "score", "score": 1.05, "confidence": 0.93})
    assert abs(score["risk"] - 0.525) < 1e-9 and score["answer"].startswith("Frustrated")
    choice_dim = {"id": "c", "type": "choice", "criteria": {"a": None, "b": None},
                  "risk": {"a": 0.0, "b": 1.0}}
    choice = interpret(choice_dim, {"type": "choice", "choice": "b", "confidence": 0.6,
                                    "probabilities": {"a": 0.2, "b": 0.8}})
    assert abs(choice["risk"] - 0.8) < 1e-9 and choice["answer"] == "b"


@check
def client_sends_documented_request():
    """The client POSTs model, state, and questions with a bearer token."""
    calls = []
    make_client(calls).evaluate("text", {"q": {"type": "noul", "instructions": "?"}})
    call = calls[0]
    assert call["url"] == "https://api.typesafe.ai/v1/systemone"
    assert call["headers"]["Authorization"] == "Bearer test-key"
    assert set(call["payload"]) == {"model", "state", "questions"}
    assert call["payload"]["model"] == "jev-latest"


@check
def client_retries_then_succeeds():
    """A 503 is retried before the successful response is returned."""
    calls = []
    client = make_client(calls, responses=[(503, "")])
    original_sleep = typesafe_client.time.sleep
    typesafe_client.time.sleep = lambda _s: None
    try:
        result = client.evaluate("text", {"q": {"type": "noul", "instructions": "?"}})
    finally:
        typesafe_client.time.sleep = original_sleep
    assert len(calls) == 2 and result["answers"]["q"]["type"] == "noul"


@check
def client_reports_api_errors():
    """401 messages and 422 validation lists become readable errors."""
    cases = [
        ((401, json.dumps({"detail": {"message": "Invalid API key"}})), "Invalid API key"),
        ((422, json.dumps({"detail": [{"loc": ["body", "questions", "q", "criteria"],
                                       "msg": "field required"}]})),
         "questions.q.criteria: field required"),
    ]
    for response, expected in cases:
        try:
            make_client([], responses=[response]).evaluate("t", {"q": {"type": "noul", "instructions": "?"}})
        except TypeSafeError as exc:
            assert expected in str(exc), str(exc)
        else:
            raise AssertionError("expected TypeSafeError")


@check
def client_rejects_missing_answers():
    """A response without an answer for every question is an error."""
    body = json.dumps({"model": "m", "answers": {}, "usage": {}})
    try:
        make_client([], responses=[(200, body)]).evaluate("t", {"q": {"type": "noul", "instructions": "?"}})
    except TypeSafeError as exc:
        assert "missing answers" in str(exc)
    else:
        raise AssertionError("expected TypeSafeError")


@check
def loads_fixture_documents():
    """Markdown and .docx fixtures in legal-test-docs load as text."""
    paths = collect_paths([FIXTURES])
    assert any(p.endswith(".docx") for p in paths) and any(p.endswith(".md") for p in paths)
    msa = [p for p in paths if p.endswith("test-msa.docx")][0]
    assert len(load_text(msa)) > 200


@check
def cli_end_to_end():
    """A full CLI run prints a table and writes a JSON report."""
    calls = []
    fixtures = os.path.join(FIXTURES, "employment")
    with tempfile.TemporaryDirectory() as tmp:
        output = os.path.join(tmp, "report.json")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
            code = evaluate.main([fixtures, "--output", output], client=make_client(calls))
        assert code == 0, stdout.getvalue()
        with open(output, encoding="utf-8") as handle:
            report = json.load(handle)
    docs = report["documents"]
    assert len(docs) == len(calls) == len(collect_paths([fixtures]))
    assert all(0 <= d["overall_risk"] <= 1 and len(d["dimensions"]) >= 10 for d in docs)
    assert "Summary" in stdout.getvalue() and "Limitation of liability" in stdout.getvalue()
    assert calls[0]["payload"]["state"]["contract_text"]


@check
def cli_dry_run_makes_no_calls():
    """--dry-run prints the request and never contacts the API."""
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
        code = evaluate.main([os.path.join(FIXTURES, "test-msa.docx"), "--dry-run"])
    assert code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["model"] == "jev-latest" and "overall_risk" in payload["questions"]


def main():
    """Run every check and return an exit code."""
    failures = 0
    for func in CHECKS:
        try:
            func()
            print(f"PASS  {func.__name__}")
        except Exception:  # noqa: BLE001
            failures += 1
            print(f"FAIL  {func.__name__}")
            traceback.print_exc()
    print(f"\n{len(CHECKS) - failures}/{len(CHECKS)} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
