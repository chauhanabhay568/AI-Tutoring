import json

from utils.quiz_utils import parse_quiz_json, score_quiz


def test_parse_quiz_json_accepts_markdown_fenced_json():
    raw = """```json
[
  {
    "question": "What is 2 + 2?",
    "options": ["3", "4"],
    "correct_answers": [1]
  }
]
```"""

    quiz = parse_quiz_json(raw, fallback_raw="[]")

    assert quiz[0]["question"] == "What is 2 + 2?"
    assert quiz[0]["correct_answers"] == [1]


def test_parse_quiz_json_falls_back_when_model_output_is_invalid():
    fallback = [{"question": "Fallback?", "options": ["Yes"], "correct_answers": [0]}]

    quiz = parse_quiz_json("not json", fallback_raw=json.dumps(fallback))

    assert quiz == fallback


def test_score_quiz_handles_single_and_multiple_answer_questions():
    quiz_data = [
        {
            "question": "Select the even number.",
            "options": ["1", "2", "3"],
            "correct_answers": [1],
        },
        {
            "question": "Select prime numbers.",
            "options": ["2", "3", "4"],
            "correct_answers": [0, 1],
        },
    ]
    user_answers = {0: "2", 1: ["3", "2"]}

    score, total, display = score_quiz(quiz_data, user_answers)

    assert score == 2
    assert total == 2
    assert "Q1: Select the even number." in display
    assert "Correct Answer(s): 2, 3" in display


def test_score_quiz_marks_wrong_multi_answer_subset_incorrect():
    quiz_data = [
        {
            "question": "Select prime numbers.",
            "options": ["2", "3", "4"],
            "correct_answers": [0, 1],
        },
    ]

    score, total, _ = score_quiz(quiz_data, {0: ["2"]})

    assert (score, total) == (0, 1)
