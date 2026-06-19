from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from evaluation.metrics import build_quiz_metrics, build_rag_metrics
from evaluation.models import DatasetValidationError, load_quiz_cases, load_rag_cases
from evaluation.reporting import summarize, write_reports


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAG_DATASET = PROJECT_ROOT / "evaluation" / "datasets" / "rag_cases.json"
DEFAULT_QUIZ_DATASET = PROJECT_ROOT / "evaluation" / "datasets" / "quiz_cases.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "evaluation" / "results"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate RAG chat and generated quizzes with DeepEval.")
    parser.add_argument("--type", choices=("rag", "quiz", "all"), default="all")
    parser.add_argument("--rag-dataset", type=Path, default=DEFAULT_RAG_DATASET)
    parser.add_argument("--quiz-dataset", type=Path, default=DEFAULT_QUIZ_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--model", default=os.getenv("DEEPEVAL_JUDGE_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--threshold", type=float, default=0.7)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate datasets without making paid LLM judge calls.",
    )
    return parser.parse_args()


def _measure(evaluation_type: str, case_id: str, test_case: Any, metrics: list[Any]) -> list[dict[str, Any]]:
    rows = []
    for metric in metrics:
        row = {
            "evaluation_type": evaluation_type,
            "case_id": case_id,
            "metric": metric.__name__,
            "score": None,
            "threshold": metric.threshold,
            "passed": None,
            "reason": "",
            "error": "",
        }
        try:
            metric.measure(test_case)
            row.update({
                "score": round(float(metric.score), 4),
                "passed": bool(metric.is_successful()),
                "reason": str(metric.reason or ""),
            })
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
        status = "ERROR" if row["error"] else ("PASS" if row["passed"] else "FAIL")
        score = "n/a" if row["score"] is None else f"{row['score']:.4f}"
        print(f"[{status}] {case_id} | {row['metric']} | {score}")
    return rows


def evaluate_rag(path: Path, model: str, threshold: float) -> list[dict[str, Any]]:
    from deepeval.test_case import LLMTestCase

    rows = []
    for case in load_rag_cases(path):
        test_case = LLMTestCase(
            input=case.input,
            actual_output=case.actual_output,
            expected_output=case.expected_output,
            retrieval_context=case.retrieval_context,
        )
        metrics = build_rag_metrics(model, threshold, case.expected_output is not None)
        rows.extend(_measure("rag", case.case_id, test_case, metrics))
    return rows


def evaluate_quizzes(path: Path, model: str, threshold: float) -> list[dict[str, Any]]:
    from deepeval.test_case import LLMTestCase

    rows = []
    for case in load_quiz_cases(path):
        test_case = LLMTestCase(
            input=case.input,
            actual_output=case.actual_output,
            expected_output=case.expected_output,
        )
        metrics = build_quiz_metrics(model, threshold, case.expected_output is not None)
        rows.extend(_measure("quiz", case.case_id, test_case, metrics))
    return rows


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args()
    if not 0 <= args.threshold <= 1:
        print("Error: --threshold must be between 0 and 1.", file=sys.stderr)
        return 2

    try:
        rag_cases = load_rag_cases(args.rag_dataset) if args.type in ("rag", "all") else []
        quiz_cases = load_quiz_cases(args.quiz_dataset) if args.type in ("quiz", "all") else []
    except DatasetValidationError as exc:
        print(f"Dataset error: {exc}", file=sys.stderr)
        return 2

    print(f"Validated {len(rag_cases)} RAG case(s) and {len(quiz_cases)} quiz case(s).")
    if args.validate_only:
        return 0
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY is required for DeepEval judge calls.", file=sys.stderr)
        return 2

    rows = []
    if rag_cases:
        rows.extend(evaluate_rag(args.rag_dataset, args.model, args.threshold))
    if quiz_cases:
        rows.extend(evaluate_quizzes(args.quiz_dataset, args.model, args.threshold))

    csv_path, json_path = write_reports(rows, args.output_dir)
    print("\nAggregate results:")
    for metric, values in summarize(rows)["metric_summary"].items():
        print(
            f"- {metric}: mean={values['mean_score']}, "
            f"pass_rate={values['pass_rate']}, errors={values['errors']}"
        )
    print(f"\nDetailed CSV: {csv_path}")
    print(f"Summary JSON: {json_path}")
    return 1 if any(row["error"] for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())

