"""Load evaluation rubrics and turn TypeSafe answers into risk scores.

A rubric is a JSON file listing dimensions. Each dimension becomes one
TypeSafe question, and each answer maps to a risk value from 0 (no risk)
to 1 (maximum risk):

- ``noul``: the probability of "yes"; phrase every noul so yes means risk.
- ``score``: the weighted position on the scale divided by the top level;
  list criteria from least to most risky.
- ``choice``: the expected risk over the option probabilities, using the
  dimension's ``risk`` map of option to weight.
"""

import json
import re

ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
TYPES = ("noul", "choice", "score")


def load_rubric(path):
    """Read and validate a rubric JSON file.

    Args:
        path: Path to the rubric JSON.

    Returns:
        The rubric dict.

    Raises:
        ValueError: If a dimension is malformed.
    """
    with open(path, encoding="utf-8") as handle:
        rubric = json.load(handle)
    dimensions = rubric.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        raise ValueError(f"{path}: rubric needs a non-empty 'dimensions' list")
    seen = set()
    for dim in dimensions:
        dim_id = dim.get("id")
        if not isinstance(dim_id, str) or not ID_PATTERN.match(dim_id):
            raise ValueError(f"{path}: dimension id {dim_id!r} must use letters, digits, '_', '.', or '-'")
        if dim_id in seen:
            raise ValueError(f"{path}: duplicate dimension id {dim_id!r}")
        seen.add(dim_id)
        if dim.get("type") not in TYPES:
            raise ValueError(f"{dim_id}: type must be one of {', '.join(TYPES)}")
        if not dim.get("instructions"):
            raise ValueError(f"{dim_id}: instructions are required")
        criteria = dim.get("criteria")
        if dim["type"] == "score" and not (isinstance(criteria, list) and len(criteria) >= 2):
            raise ValueError(f"{dim_id}: score criteria must list at least two levels")
        if dim["type"] == "choice":
            if not (isinstance(criteria, dict) and criteria):
                raise ValueError(f"{dim_id}: choice criteria must map options to descriptions")
            risk = dim.get("risk")
            if not isinstance(risk, dict) or set(risk) != set(criteria):
                raise ValueError(f"{dim_id}: choice needs a 'risk' weight for every option")
            if not all(isinstance(w, (int, float)) and 0 <= w <= 1 for w in risk.values()):
                raise ValueError(f"{dim_id}: risk weights must be numbers from 0 to 1")
        if dim["type"] == "noul" and criteria is not None:
            if not (isinstance(criteria, dict) and set(criteria) <= {"true", "false"}):
                raise ValueError(f"{dim_id}: noul criteria may only have 'true' and 'false' keys")
    return rubric


def build_questions(rubric):
    """Return the TypeSafe ``questions`` map for a rubric.

    Args:
        rubric: A rubric dict from ``load_rubric``.

    Returns:
        Dimension id to question payload, in rubric order.
    """
    questions = {}
    for dim in rubric["dimensions"]:
        question = {"type": dim["type"], "instructions": dim["instructions"]}
        if dim.get("criteria") is not None:
            question["criteria"] = dim["criteria"]
        questions[dim["id"]] = question
    return questions


def level_text(level):
    """Return a short display string for a score level, which may be structured."""
    if isinstance(level, str):
        return level
    if isinstance(level, dict):
        for key in ("summary", "label", "what"):
            if isinstance(level.get(key), str):
                return level[key]
    return json.dumps(level)


def interpret(dim, answer):
    """Summarize one TypeSafe answer as display text and a risk value.

    Args:
        dim: The rubric dimension that produced the question.
        answer: TypeSafe's typed answer for that question.

    Returns:
        ``{"answer": str, "risk": 0..1, "confidence": 0..1}``.

    Raises:
        ValueError: If the answer type does not match the dimension.
    """
    kind = dim["type"]
    if answer.get("type") != kind:
        raise ValueError(f"{dim['id']}: expected a {kind} answer, got {answer.get('type')!r}")
    if kind == "noul":
        probability = float(answer["noul"])
        # Nouls report no confidence; distance from 0.5 serves as one.
        return {
            "answer": f"{'yes' if probability >= 0.5 else 'no'} (p={probability:.2f})",
            "risk": probability,
            "confidence": abs(probability - 0.5) * 2,
        }
    if kind == "score":
        top = len(dim["criteria"]) - 1
        position = float(answer["score"])
        nearest = dim["criteria"][min(top, max(0, round(position)))]
        return {
            "answer": f"{level_text(nearest)} ({position:.2f}/{top})",
            "risk": position / top,
            "confidence": float(answer.get("confidence", 0.0)),
        }
    probabilities = answer.get("probabilities") or {answer["choice"]: 1.0}
    total = sum(probabilities.values()) or 1.0
    risk = sum(dim["risk"].get(opt, 0.0) * p for opt, p in probabilities.items()) / total
    return {
        "answer": answer["choice"],
        "risk": risk,
        "confidence": float(answer.get("confidence", 0.0)),
    }
