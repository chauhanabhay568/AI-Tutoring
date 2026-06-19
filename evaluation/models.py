from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class DatasetValidationError(ValueError):
    """Raised when an evaluation dataset is malformed."""


def _required_text(item: dict[str, Any], field: str, case_id: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise DatasetValidationError(
            f"Case '{case_id}' requires a non-empty string field '{field}'."
        )
    return value.strip()


@dataclass(frozen=True)
class RagCase:
    case_id: str
    input: str
    actual_output: str
    retrieval_context: list[str]
    expected_output: str | None = None

    @classmethod
    def from_dict(cls, item: dict[str, Any], index: int) -> "RagCase":
        case_id = str(item.get("id") or f"rag_{index + 1}")
        contexts = item.get("retrieval_context")
        if not isinstance(contexts, list) or not contexts:
            raise DatasetValidationError(
                f"Case '{case_id}' requires a non-empty retrieval_context list."
            )
        if any(not isinstance(chunk, str) or not chunk.strip() for chunk in contexts):
            raise DatasetValidationError(
                f"Case '{case_id}' retrieval_context must contain non-empty strings."
            )

        expected = item.get("expected_output")
        if expected is not None and (not isinstance(expected, str) or not expected.strip()):
            raise DatasetValidationError(
                f"Case '{case_id}' expected_output must be a non-empty string when set."
            )

        return cls(
            case_id=case_id,
            input=_required_text(item, "input", case_id),
            actual_output=_required_text(item, "actual_output", case_id),
            expected_output=expected.strip() if expected else None,
            retrieval_context=[chunk.strip() for chunk in contexts],
        )


@dataclass(frozen=True)
class QuizCase:
    case_id: str
    input: str
    actual_output: str
    expected_output: str | None = None

    @classmethod
    def from_dict(cls, item: dict[str, Any], index: int) -> "QuizCase":
        case_id = str(item.get("id") or f"quiz_{index + 1}")
        actual = item.get("actual_output")
        if isinstance(actual, (dict, list)):
            actual = json.dumps(actual, ensure_ascii=True, indent=2)
        if not isinstance(actual, str) or not actual.strip():
            raise DatasetValidationError(
                f"Case '{case_id}' requires actual_output as text, an object, or a list."
            )

        expected = item.get("expected_output")
        if isinstance(expected, (dict, list)):
            expected = json.dumps(expected, ensure_ascii=True, indent=2)
        if expected is not None and (not isinstance(expected, str) or not expected.strip()):
            raise DatasetValidationError(
                f"Case '{case_id}' expected_output must be valid non-empty content."
            )

        return cls(
            case_id=case_id,
            input=_required_text(item, "input", case_id),
            actual_output=actual.strip(),
            expected_output=expected.strip() if expected else None,
        )


def load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise DatasetValidationError(f"Dataset not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DatasetValidationError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, list) or not data:
        raise DatasetValidationError(f"Dataset {path} must be a non-empty JSON list.")
    if any(not isinstance(item, dict) for item in data):
        raise DatasetValidationError(f"Every entry in {path} must be a JSON object.")
    return data


def load_rag_cases(path: Path) -> list[RagCase]:
    return [RagCase.from_dict(item, index) for index, item in enumerate(load_json_list(path))]


def load_quiz_cases(path: Path) -> list[QuizCase]:
    return [QuizCase.from_dict(item, index) for index, item in enumerate(load_json_list(path))]

