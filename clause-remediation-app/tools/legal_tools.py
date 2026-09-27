"""Legal analysis tools for the Legal Agent.

Uses Claude API with domain-specific prompts informed by
Claude for Legal plugin patterns.
"""

import json
import os

import anthropic

# Model used for every Legal Agent call. Override with the CLAUDE_MODEL env var.
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")

_client = None


def _get_client():
    """Get or create the Anthropic client singleton."""
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


CLAUSE_SYSTEM = """You are a legal document analyst specializing in contract clause identification.
Given document text and a target clause type, identify whether the clause exists,
extract its text, and note its location. Be precise about clause boundaries.

Respond with JSON only:
{
  "found": true/false,
  "clause_text": "exact clause text if found",
  "section": "section number or heading if identifiable",
  "confidence": 0.0-1.0
}"""

ASSESS_SYSTEM = """You are a legal compliance analyst. Given a clause and a target standard,
determine whether the clause meets the standard or needs updating.

Respond with JSON only:
{
  "needs_update": true/false,
  "reason": "specific reason",
  "risk_level": "low/medium/high",
  "current_reference": "what the clause currently references",
  "target_reference": "what it should reference"
}"""

DRAFT_SYSTEM = """You are a legal drafting specialist. Given an original clause, a target standard,
and document context, draft replacement language that:
- Preserves the structure and style of the original
- Updates only the specific reference that needs changing
- Maintains all other terms and conditions
- Uses plain language consistent with the document

Respond with JSON only:
{
  "replacement_clause": "the full replacement clause text",
  "changes_summary": "brief description of what changed",
  "find": "exact text to find in the original",
  "replace": "exact replacement text"
}"""

REVIEW_SYSTEM = """You are a legal QA reviewer. Compare original and modified text to verify:
- Only intended changes were made
- No unintended modifications to surrounding language
- Replacement language is legally sound
- Defined terms and cross-references remain consistent

Respond with JSON only:
{
  "approved": true/false,
  "issues": ["list of issues if any"],
  "notes": "reviewer notes"
}"""


def coerce_confidence(value):
    """Convert a model-reported confidence value to a float.

    Args:
        value: Confidence as returned by the model (float, int, numeric
            string such as "0.8" or "80%", or None).

    Returns:
        Float between 0.0 and 1.0, or None if the value is not numeric.
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        is_percent = text.endswith("%")
        try:
            number = float(text.rstrip("%").strip())
        except ValueError:
            return None
        if is_percent:
            number /= 100
    else:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
    if number != number:  # NaN
        return None
    return max(0.0, min(1.0, number))


def format_confidence(value):
    """Format a confidence value as a percentage for narration.

    Args:
        value: Raw confidence value from the model.

    Returns:
        String such as "85%", or "n/a" when the value is not numeric.
    """
    number = coerce_confidence(value)
    return "n/a" if number is None else f"{number:.0%}"


def _parse_json(text):
    """Parse a JSON object from model output without raising.

    Args:
        text: Raw response text, optionally wrapped in a code fence.

    Returns:
        Parsed dict, or a dict with an "error" key when parsing fails.
    """
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0].strip()
    candidates = [text]
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        candidates.append(text[start:end])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {
        "error": "Could not parse JSON from Claude response",
        "raw_response": text[:500],
    }


def _call_claude(system, user_message, max_tokens=1024):
    """Make a Claude API call and parse JSON response.

    Args:
        system: System prompt.
        user_message: User message content.
        max_tokens: Maximum response tokens.

    Returns:
        Parsed JSON dict from Claude's response. On an empty or unparseable
        response, a dict with an "error" key is returned instead of raising.
    """
    client = _get_client()
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    text = "".join(
        getattr(block, "text", "") for block in (response.content or [])
        if getattr(block, "type", None) == "text"
    )
    if not text.strip():
        return {
            "error": "Empty response from Claude",
            "stop_reason": getattr(response, "stop_reason", None),
        }
    return _parse_json(text)


def identify_clause(doc_text, clause_type):
    """Find a specific clause type in document text.

    Args:
        doc_text: Full document text.
        clause_type: Type of clause to find (e.g., 'arbitration').

    Returns:
        Dict with found, clause_text, section, confidence.
    """
    prompt = (
        f"Find the {clause_type} clause in this document.\n\n"
        f"Document text:\n{doc_text[:8000]}"
    )
    return _call_claude(CLAUSE_SYSTEM, prompt)


def assess_clause(clause_text, standard):
    """Determine if a clause meets a given standard.

    Args:
        clause_text: The clause text to assess.
        standard: The standard to check against.

    Returns:
        Dict with needs_update, reason, risk_level, current_reference, target_reference.
    """
    prompt = (
        f"Assess whether this clause meets the following standard.\n\n"
        f"Standard: {standard}\n\n"
        f"Clause text:\n{clause_text}"
    )
    return _call_claude(ASSESS_SYSTEM, prompt)


def draft_replacement(original_clause, target_standard, context):
    """Generate replacement clause language.

    Args:
        original_clause: The original clause text.
        target_standard: What the clause should reference.
        context: Document type and context description.

    Returns:
        Dict with replacement_clause, changes_summary, find, replace.
    """
    prompt = (
        f"Draft replacement language for this clause.\n\n"
        f"Original clause:\n{original_clause}\n\n"
        f"Target standard: {target_standard}\n\n"
        f"Document context: {context}"
    )
    return _call_claude(DRAFT_SYSTEM, prompt, max_tokens=2048)


def review_redline(original_text, modified_text, intended_changes):
    """QA a set of changes against the original.

    Args:
        original_text: Original document text (or relevant excerpt).
        modified_text: Modified document text.
        intended_changes: Description of what changes were intended.

    Returns:
        Dict with approved, issues, notes.
    """
    prompt = (
        f"Review these changes for correctness.\n\n"
        f"Intended changes: {intended_changes}\n\n"
        f"Original:\n{original_text[:4000]}\n\n"
        f"Modified:\n{modified_text[:4000]}"
    )
    return _call_claude(REVIEW_SYSTEM, prompt)
