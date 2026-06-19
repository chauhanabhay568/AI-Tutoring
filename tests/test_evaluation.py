import json

import pytest

from evaluation.models import DatasetValidationError, QuizCase, RagCase, load_quiz_cases, load_rag_cases
from evaluation.reporting import summarize, write_reports


def test_bundled_datasets_are_valid():
    rag_cases = load_rag_cases(__import__("pathlib").Path("evaluation/datasets/rag_cases.json"))
    quiz_cases = load_quiz_cases(__import__("pathlib").Path("evaluation/datasets/quiz_cases.json"))

    assert len(rag_cases) >= 2
    assert len(quiz_cases) >= 2


def test_rag_case_rejects_string_context():
    with pytest.raises(DatasetValidationError, match="retrieval_context"):
        RagCase.from_dict(
            {"input": "Question", "actual_output": "Answer", "retrieval_context": "chunk"},
            0,
        )


def test_quiz_case_serializes_structured_output():
    case = QuizCase.from_dict(
        {"input": "Generate a quiz", "actual_output": [{"question": "Q"}]},
        0,
    )
    assert json.loads(case.actual_output) == [{"question": "Q"}]


def test_summary_and_reports(tmp_path):
    rows = [
        {"evaluation_type": "rag", "case_id": "one", "metric": "FaithfulnessMetric", "score": 0.8, "threshold": 0.7, "passed": True, "reason": "Grounded", "error": ""},
        {"evaluation_type": "rag", "case_id": "two", "metric": "FaithfulnessMetric", "score": 0.6, "threshold": 0.7, "passed": False, "reason": "Unsupported", "error": ""},
    ]

    metric_summary = summarize(rows)["metric_summary"]["FaithfulnessMetric"]
    assert metric_summary["mean_score"] == 0.7
    assert metric_summary["pass_rate"] == 0.5

    csv_path, json_path = write_reports(rows, tmp_path)
    assert csv_path.exists()
    assert json_path.exists()

