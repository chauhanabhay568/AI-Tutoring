from __future__ import annotations

from typing import Any


def build_rag_metrics(model: str, threshold: float, has_expected_output: bool) -> list[Any]:
    """Build the RAG triad, plus reference-based metrics when labels exist."""
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        ContextualPrecisionMetric,
        ContextualRecallMetric,
        ContextualRelevancyMetric,
        FaithfulnessMetric,
    )

    common = {
        "model": model,
        "threshold": threshold,
        "include_reason": True,
        "async_mode": False,
    }
    metrics: list[Any] = [
        AnswerRelevancyMetric(**common),
        FaithfulnessMetric(**common),
        ContextualRelevancyMetric(**common),
    ]
    if has_expected_output:
        metrics.extend([
            ContextualPrecisionMetric(**common),
            ContextualRecallMetric(**common),
        ])
    return metrics


def build_quiz_metrics(model: str, threshold: float, has_expected_output: bool) -> list[Any]:
    """Build explicit G-Eval rubrics for generated quiz quality."""
    from deepeval.metrics import GEval
    from deepeval.test_case import SingleTurnParams

    input_output = [SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT]
    metrics: list[Any] = [
        GEval(
            name="Quiz Topic Relevance",
            evaluation_steps=[
                "Identify the requested subject, topic, difficulty, understanding level, focus, and question count from the input.",
                "Check that every generated question tests the requested subject and topic.",
                "Penalize unrelated questions, incorrect question counts, and outputs that ignore the requested focus or learner level.",
                "Assign a high score only when the quiz closely follows all stated requirements.",
            ],
            evaluation_params=input_output,
            model=model,
            threshold=threshold,
            async_mode=False,
        ),
        GEval(
            name="Quiz Difficulty Alignment",
            evaluation_steps=[
                "Infer the requested difficulty and student understanding level from the input.",
                "Inspect the knowledge and reasoning needed to answer each generated question.",
                "Penalize questions that are substantially easier or harder than requested.",
                "Score the overall consistency of difficulty across the quiz.",
            ],
            evaluation_params=input_output,
            model=model,
            threshold=threshold,
            async_mode=False,
        ),
        GEval(
            name="Quiz Question Quality",
            evaluation_steps=[
                "Check that each question is clear, self-contained, and has enough information to answer.",
                "Check that answer options are plausible, distinct, grammatical, and free of accidental clues.",
                "Check that the marked correct answer indices are valid and that each question has at least one correct answer.",
                "Penalize ambiguity, duplication, malformed JSON structure, and trick wording unrelated to learning.",
            ],
            evaluation_params=input_output,
            model=model,
            threshold=threshold,
            async_mode=False,
        ),
    ]

    correctness_params = list(input_output)
    correctness_steps = [
        "Check the factual and conceptual correctness of every generated question and option.",
        "Verify that every marked correct answer is genuinely correct and that no unmarked option is also correct unless multiple answers are explicitly allowed.",
        "Penalize factual errors, contradictory options, invalid answer indices, and ambiguous answer keys.",
    ]
    if has_expected_output:
        correctness_params.append(SingleTurnParams.EXPECTED_OUTPUT)
        correctness_steps.append(
            "Use the expected output as the authoritative reference while allowing equivalent wording."
        )
    else:
        correctness_steps.append(
            "Use established subject knowledge to judge correctness because no reference answer was supplied."
        )
    metrics.append(
        GEval(
            name="Quiz Correctness",
            evaluation_steps=correctness_steps,
            evaluation_params=correctness_params,
            model=model,
            threshold=threshold,
            async_mode=False,
        )
    )
    return metrics

