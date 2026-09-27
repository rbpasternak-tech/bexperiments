"""Minimal client for TypeSafe's System One API (POST /v1/systemone).

System One models such as Jev evaluate one ``state`` against a map of typed
questions (``noul``, ``choice``, ``score``) and return one typed answer per
question, plus token usage. They generate no free text.

Request::

    {"model": "jev-latest",
     "state": "<string, object, or array>",
     "questions": {"<id>": {"type": "noul|choice|score",
                            "instructions": "...",
                            "criteria": ...}}}

Response::

    {"model": "jev-1.13.0",
     "answers": {"<id>": {"type": "noul", "noul": 0.95}},
     "usage": {"input_tokens": 426, "output_tokens": 73}}
"""

import json
import os
import time
import urllib.error
import urllib.request

DEFAULT_API_BASE = "https://api.typesafe.ai"
DEFAULT_MODEL = "jev-latest"
RETRY_STATUSES = {429, 500, 502, 503, 504}


class TypeSafeError(Exception):
    """Raised when the TypeSafe API rejects a request or returns bad data."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def error_message(status, body):
    """Turn a TypeSafe error body into a readable message.

    TypeSafe reports failures under ``detail``: a dict with ``message`` for
    usage errors, or a list of ``{loc, msg}`` entries for 422 validation.
    """
    try:
        detail = json.loads(body).get("detail")
    except (ValueError, AttributeError):
        detail = None
    if isinstance(detail, dict) and detail.get("message"):
        text = detail["message"]
    elif isinstance(detail, list):
        parts = []
        for part in detail:
            if not isinstance(part, dict):
                parts.append(str(part))
                continue
            loc = ".".join(str(s) for s in part.get("loc", []) if s != "body")
            msg = part.get("msg") or json.dumps(part)
            parts.append(f"{loc}: {msg}" if loc else msg)
        text = "; ".join(parts)
    else:
        text = (body or "").strip()[:300] or "no response body"
    return f"TypeSafe API error {status}: {text}"


def urllib_transport(url, headers, payload, timeout):
    """POST ``payload`` as JSON and return ``(status, body_text)``."""
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


class TypeSafeClient:
    """Sends System One evaluations and validates the response shape."""

    def __init__(self, api_key=None, api_base=None, model=DEFAULT_MODEL,
                 timeout=60, max_retries=3, transport=urllib_transport):
        self.api_key = api_key or os.environ.get("TYPESAFE_API_KEY")
        self.api_base = (api_base or os.environ.get("TYPESAFE_API_BASE")
                         or DEFAULT_API_BASE).rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.transport = transport

    def evaluate(self, state, questions):
        """Evaluate one state against a map of typed questions.

        Args:
            state: The text, object, or array for TypeSafe to judge.
            questions: Question id to ``{type, instructions, criteria}``.

        Returns:
            The response dict with ``model``, ``answers``, and ``usage``.

        Raises:
            TypeSafeError: If the key is missing, the API returns an error
                after retries, or the response lacks an answer.
        """
        if not self.api_key:
            raise TypeSafeError("TYPESAFE_API_KEY is not set")
        payload = {"model": self.model, "state": state, "questions": questions}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        url = f"{self.api_base}/v1/systemone"

        for attempt in range(self.max_retries + 1):
            try:
                status, body = self.transport(url, headers, payload, self.timeout)
            except OSError as exc:
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    continue
                raise TypeSafeError(f"Could not reach TypeSafe at {url}: {exc}") from exc
            if status in RETRY_STATUSES and attempt < self.max_retries:
                time.sleep(2 ** attempt)
                continue
            break

        if status != 200:
            raise TypeSafeError(error_message(status, body), status=status)
        try:
            result = json.loads(body)
        except ValueError as exc:
            raise TypeSafeError("TypeSafe returned a non-JSON response") from exc
        if not (isinstance(result, dict) and isinstance(result.get("answers"), dict)
                and isinstance(result.get("usage"), dict)):
            raise TypeSafeError("TypeSafe response is missing answers or usage")
        missing = sorted(set(questions) - set(result["answers"]))
        if missing:
            raise TypeSafeError(f"TypeSafe response is missing answers for: {', '.join(missing)}")
        return result
