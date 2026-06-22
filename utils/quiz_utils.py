from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, MutableMapping

import openai
import streamlit as st

from utils.llm_client import LLMClient

logger = logging.getLogger(__name__)

BUILTIN_FALLBACK_QUIZ = json.dumps(
    [
        {
            "question": "What is the primary purpose of practicing quiz questions?",
            "options": [
                "To memorize every answer only once",
                "To check understanding and identify gaps",
                "To avoid reviewing the material",
            ],
            "correct_answers": [1],
        },
        {
            "question": "Which study habit is most effective for long-term retention?",
            "options": [
                "Spaced practice over time",
                "Reading the notes once",
                "Skipping review sessions",
            ],
            "correct_answers": [0],
        },
    ],
    indent=2,
)


# ── Session state ─────────────────────────────────────────────────────────────

def init_quiz_session_state(session_state: MutableMapping[str, Any] | None = None) -> None:
    """Initialise all session-state keys needed by the quiz page."""
    state = session_state if session_state is not None else st.session_state
    defaults: dict[str, Any] = {
        "quiz_form_submitted": False,
        "quiz_result_submitted": False,
        "quiz_subject": None,
        "quiz_topic": None,
        "quiz_level": None,
        "quiz_understanding": None,
        "quiz_num_questions": None,
        "quiz_focus": None,
        "quiz_already_generated": False,
        "quiz_raw_response": None,
    }
    for key, value in defaults.items():
        if key not in state:
            state[key] = value


def clear_quiz_session_state(session_state: MutableMapping[str, Any] | None = None) -> None:
    """Reset all quiz-related session-state keys."""
    state = session_state if session_state is not None else st.session_state
    keys = [
        "quiz_form_submitted", "quiz_result_submitted",
        "quiz_subject", "quiz_topic", "quiz_level",
        "quiz_understanding", "quiz_num_questions", "quiz_focus",
        "quiz_already_generated", "quiz_raw_response",
        "quiz_data", "quiz_user_answers",
    ]
    for key in keys:
        if key in state:
            state[key] = False if "submitted" in key or "generated" in key else None


# ── Dummy quiz fallback ───────────────────────────────────────────────────────

@st.cache_resource
def load_dummy_quiz() -> str:
    """Load the fallback quiz from disk (used when the API call fails)."""
    path = Path("pages/dummyquiz.txt")
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeDecodeError) as exc:
        logger.warning("Using built-in fallback quiz because %s could not be read: %s", path, exc)
        return BUILTIN_FALLBACK_QUIZ


# ── Quiz generation ───────────────────────────────────────────────────────────

def generate_quiz(
    subject: str,
    topic: str,
    level: str,
    understanding: str,
    num_questions: int,
    focus: str,
    llm_client: LLMClient,
) -> str | None:
    """
    Generate a JSON quiz based on the student's preferences.
    Returns the raw JSON string or None on failure.
    """
    prompt = (
        f"Create a quiz with {num_questions} questions based on:\n"
        f"Subject: {subject}\nTopic: {topic}\n"
        f"Difficulty: {level}\nUnderstanding Level: {understanding}\n"
        f"Focus: {focus}\n\n"
        f"Format: a JSON array where each element has:\n"
        f"  - 'question': the question text\n"
        f"  - 'options': list of answer choices\n"
        f"  - 'correct_answers': list of correct option indices (0-based)\n"
        f"Return ONLY the JSON array. No markdown, no explanation."
    )
    try:
        response = llm_client.complete(
            messages=[
                {"role": "system", "content": "You are a quiz generator. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content
    except (openai.OpenAIError, AttributeError, IndexError, KeyError, ValueError) as exc:
        logger.exception("Failed to generate quiz: %s", exc)
        return None


def parse_quiz_json(raw: str | None, fallback_raw: str) -> list[dict[str, Any]]:
    """
    Safely parse the LLM's JSON response.
    Strips markdown code fences if present, then falls back to the dummy quiz.
    """
    try:
        clean = re.sub(r"```(?:json)?", "", raw or "").strip()
        parsed = json.loads(clean)
        if isinstance(parsed, list):
            return parsed
        return []
    except (json.JSONDecodeError, TypeError, ValueError):
        try:
            parsed = json.loads(fallback_raw)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.exception("Failed to parse both generated quiz and fallback quiz: %s", exc)
            return []


# ── Quiz evaluation ───────────────────────────────────────────────────────────

def score_quiz(quiz_data: list[dict[str, Any]], user_answers: dict[int, Any]) -> tuple[int, int, str]:
    """Return (score, total, display_string) for a completed quiz."""
    score = 0
    total = len(quiz_data)
    lines: list[str] = []

    for idx, question in enumerate(quiz_data):
        correct_indices = question["correct_answers"]
        correct_answers = [question["options"][int(i)] for i in correct_indices]
        user_answer = user_answers.get(idx)

        if isinstance(user_answer, list):
            if set(user_answer) == set(correct_answers):
                score += 1
        else:
            if user_answer in correct_answers:
                score += 1

        lines.append(f"Q{idx + 1}: {question['question']}")
        lines.append(f"Your Answer: {user_answer}")
        lines.append(f"Correct Answer(s): {', '.join(correct_answers)}\n")

    return score, total, "\n".join(lines)


def get_quiz_feedback(
    display_string: str,
    session_data: MutableMapping[str, Any],
    score_ratio: float,
    llm_client: LLMClient,
) -> str:
    """Generate personalised study recommendations after the quiz."""
    prompt = f"""
The student completed a quiz:
Subject: {session_data['quiz_subject']}
Topic: {session_data['quiz_topic']}
Level: {session_data['quiz_level']}
Understanding: {session_data['quiz_understanding']}
Focus: {session_data['quiz_focus']}
Score: {score_ratio * 100:.1f}%

Quiz results:
{display_string}

Give three personalised study recommendations based on their weak areas.
Each recommendation must be a complete, actionable sentence.
"""
    try:
        response = llm_client.complete(
            messages=[
                {"role": "system", "content": "You are a study coach providing personalised recommendations."},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content
    except (openai.OpenAIError, AttributeError, IndexError, KeyError, ValueError) as exc:
        logger.exception("Could not generate quiz feedback: %s", exc)
        return "Could not generate feedback right now. Please try again later."
