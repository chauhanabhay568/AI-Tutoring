import json
import re
import streamlit as st
import openai


# ── Session state ─────────────────────────────────────────────────────────────

def init_quiz_session_state():
    """Initialise all session-state keys needed by the quiz page."""
    defaults = {
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
        if key not in st.session_state:
            st.session_state[key] = value


def clear_quiz_session_state():
    """Reset all quiz-related session-state keys."""
    keys = [
        "quiz_form_submitted", "quiz_result_submitted",
        "quiz_subject", "quiz_topic", "quiz_level",
        "quiz_understanding", "quiz_num_questions", "quiz_focus",
        "quiz_already_generated", "quiz_raw_response",
        "quiz_data", "quiz_user_answers",
    ]
    for key in keys:
        if key in st.session_state:
            st.session_state[key] = False if "submitted" in key or "generated" in key else None


# ── Dummy quiz fallback ───────────────────────────────────────────────────────

@st.cache_resource
def load_dummy_quiz():
    """Load the fallback quiz from disk (used when the API call fails)."""
    with open("pages/dummyquiz.txt", "r") as f:
        return f.read()


# ── Quiz generation ───────────────────────────────────────────────────────────

def generate_quiz(subject, topic, level, understanding, num_questions, focus):
    """
    Call GPT-4 to generate a JSON quiz based on the student's preferences.
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
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a quiz generator. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Failed to generate quiz: {e}")
        return None


def parse_quiz_json(raw, fallback_raw):
    """
    Safely parse the LLM's JSON response.
    Strips markdown code fences if present, then falls back to the dummy quiz.
    """
    try:
        clean = re.sub(r"```(?:json)?", "", raw).strip()
        return json.loads(clean)
    except (json.JSONDecodeError, TypeError):
        try:
            return json.loads(fallback_raw)
        except Exception:
            return []


# ── Quiz evaluation ───────────────────────────────────────────────────────────

def score_quiz(quiz_data, user_answers):
    """Return (score, total, display_string) for a completed quiz."""
    score = 0
    total = len(quiz_data)
    lines = []

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


def get_quiz_feedback(display_string, session_data, score_ratio):
    """Call GPT-4 to generate personalised study recommendations after the quiz."""
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
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a study coach providing personalised recommendations."},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Could not generate feedback: {e}"
