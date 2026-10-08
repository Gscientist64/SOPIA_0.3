"""Tolerant JSON parsing for LLM output.

Small local models routinely produce JSON that is *almost* valid: a trailing
comma, prose before the array, a newline inside a string, or one broken object.
Rather than discard the whole response, these helpers salvage whatever they can.
"""

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_TRAILING_COMMA = re.compile(r",\s*([}\]\]])")


def strip_code_fence(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
        if text[:4].lower() == "json":
            text = text[4:]
    return text.strip()


def _loads(text: str) -> Any:
    """Try hard to decode ``text`` as JSON, tolerating a trailing comma."""
    for variant in (text, _TRAILING_COMMA.sub(r"\1", text)):
        try:
            return json.loads(variant)
        except json.JSONDecodeError:
            continue
    return None


def _balanced_objects(text: str) -> list[str]:
    """Extract each top-level ``{...}`` region, ignoring braces inside strings."""
    objects: list[str] = []
    depth = 0
    start: int | None = None
    in_string = False
    escaped = False

    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                objects.append(text[start : index + 1])
                start = None
    return objects


def _salvage_objects(text: str) -> list[dict[str, Any]]:
    salvaged: list[dict[str, Any]] = []
    for candidate in _balanced_objects(text):
        parsed = _loads(candidate)
        if isinstance(parsed, dict):
            salvaged.append(parsed)
    return salvaged


def parse_json_object(raw: str) -> dict[str, Any]:
    text = strip_code_fence(raw)
    parsed = _loads(text)
    if isinstance(parsed, dict):
        return parsed
    salvaged = _salvage_objects(text)
    if salvaged:
        return salvaged[0]
    logger.warning("Could not parse a JSON object from model output: %r", text[:400])
    return {}


def parse_json_array(raw: str) -> list[dict[str, Any]]:
    text = strip_code_fence(raw)
    start, end = text.find("["), text.rfind("]")
    candidates = [text]
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])

    for candidate in candidates:
        parsed = _loads(candidate)
        if isinstance(parsed, dict):
            parsed = [parsed]
        if isinstance(parsed, list):
            objects = [item for item in parsed if isinstance(item, dict)]
            if objects:
                if len(objects) != len(parsed):
                    logger.warning(
                        "Dropped %d non-object array entries. Sample: %r",
                        len(parsed) - len(objects),
                        parsed[:2],
                    )
                return objects

    salvaged = _salvage_objects(text)
    if salvaged:
        logger.warning("Salvaged %d object(s) from malformed JSON output.", len(salvaged))
        return salvaged

    logger.warning("Could not parse any JSON objects from model output: %r", text[:400])
    return []


# Small models frequently rename the keys we ask for. Rather than fail, accept the
# common aliases and normalise every question into one canonical shape.
_PROMPT_KEYS = ("prompt", "question", "question_text", "questionText", "text", "title")
_OPTION_KEYS = ("options", "choices", "answers", "answer_options", "alternatives")
_CORRECT_KEYS = ("correct_answer", "correctAnswer", "answer", "correct", "correct_option")
_EXPLANATION_KEYS = ("explanation", "rationale", "reason", "justification")
_TYPE_KEYS = ("question_type", "questionType", "type", "kind")
_TOPIC_KEYS = ("topic", "subject", "category")


def _first_present(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def normalise_question(item: dict[str, Any]) -> dict[str, Any]:
    """Map a model-generated question onto SOPIA's canonical keys."""
    options = _first_present(item, _OPTION_KEYS)
    if isinstance(options, dict):
        options = list(options.values())
    if not isinstance(options, list):
        options = []

    prompt = _first_present(item, _PROMPT_KEYS)
    return {
        "prompt": str(prompt).strip() if prompt is not None else "",
        "question_type": str(_first_present(item, _TYPE_KEYS) or "mcq"),
        "options": [str(option) for option in options],
        "correct_answer": _first_present(item, _CORRECT_KEYS),
        "explanation": _first_present(item, _EXPLANATION_KEYS),
        "topic": _first_present(item, _TOPIC_KEYS),
        "difficulty": item.get("difficulty"),
    }


def normalise_questions(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalise a batch, discarding anything without usable question text."""
    usable = [item for item in items if isinstance(item, dict)]
    normalised = [normalise_question(item) for item in usable]
    kept = [q for q in normalised if q["prompt"]]
    if len(kept) != len(items):
        logger.warning(
            "Discarded %d of %d generated questions. Rejected sample: %s",
            len(items) - len(kept),
            len(items),
            str(items[:2])[:500],
        )
    return kept

