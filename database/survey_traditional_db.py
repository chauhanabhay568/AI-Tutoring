import sqlite3
import pandas as pd

DB_PATH = "database_files/survey_traditional.db"


def init_survey_traditional_db():
    """Create the traditional-teaching survey table if it does not exist."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS survey_responses (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    name                TEXT,
                    email               TEXT,
                    course_level        TEXT,
                    general_proficiency TEXT,
                    python_proficiency  TEXT,
                    teaching_methods    TEXT,
                    effective_learning  TEXT,
                    satisfaction        TEXT,
                    q1 INTEGER, q2 INTEGER, q3 INTEGER, q4 INTEGER, q5 INTEGER,
                    q6 INTEGER, q7 INTEGER, q8 INTEGER, q9 INTEGER, q10 INTEGER
                )
            """)
            conn.commit()
    except sqlite3.Error as e:
        print(f"[survey_traditional_db] init error: {e}")


def insert_survey_response(data):
    """Insert one survey response. `data` is the dict from the page."""
    questions = [
        "Traditional teaching methods allow for personalized learning tailored to my needs.",
        "In traditional teaching methods, I am able to learn at my own pace.",
        "Through traditional teaching methods, I receive real-time personalized feedback that enhances my understanding.",
        "In traditional teaching methods, my confidence grows as I complete my learning.",
        "I enhance my motivation when learning through traditional teaching methods.",
        "I am highly engaged when learning through traditional teaching methods.",
        "In traditional teaching methods, the explanations for my mistakes are clear.",
        "When using traditional teaching methods, the specific challenges I face are effectively addressed.",
        "In traditional teaching methods, enough exercises related to the topic are provided to enhance my skills.",
        "In general, my learning preferences are considered when learning in traditional teaching environments.",
    ]
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO survey_responses
                    (name, email, course_level, general_proficiency, python_proficiency,
                     teaching_methods, effective_learning, satisfaction,
                     q1, q2, q3, q4, q5, q6, q7, q8, q9, q10)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data.get("Name"), data.get("Email"),
                    data.get("Course Level"), data.get("General Proficiency"),
                    data.get("Python Proficiency"), data.get("Teaching Methods"),
                    data.get("Effective Learning"), data.get("Satisfaction"),
                    *[data.get(q, 0) for q in questions],
                ),
            )
            conn.commit()
    except sqlite3.Error as e:
        print(f"[survey_traditional_db] insert error: {e}")


def get_all_responses():
    """Return all survey responses as a DataFrame."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            return pd.read_sql_query("SELECT * FROM survey_responses", conn)
    except sqlite3.Error as e:
        print(f"[survey_traditional_db] fetch error: {e}")
        return pd.DataFrame()
