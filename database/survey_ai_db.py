import sqlite3
import pandas as pd

DB_PATH = "database_files/survey_ai.db"


def init_survey_ai_db():
    """Create the AI-tutoring survey table if it does not exist."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS survey_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT, email TEXT,
                    ai_personalized_learning INTEGER, ai_self_paced_learning INTEGER,
                    ai_real_time_feedback INTEGER, ai_confidence_growth INTEGER,
                    ai_motivation INTEGER, ai_engagement INTEGER,
                    ai_clear_explanations INTEGER, ai_address_challenges INTEGER,
                    ai_enough_exercises INTEGER, ai_considers_preferences INTEGER,
                    ai_no_technical_issues INTEGER, ai_user_friendly INTEGER,
                    compare_personalized INTEGER, compare_engagement INTEGER,
                    compare_understanding INTEGER, compare_support INTEGER,
                    compare_effectiveness INTEGER,
                    open_likes TEXT, open_dislikes TEXT, open_improvements TEXT,
                    open_personalization TEXT, feedback_importance TEXT,
                    feedback_traditional_support TEXT, feedback_ai_improvement TEXT,
                    feedback_recommendation TEXT, feedback_preference TEXT,
                    feedback_additional TEXT
                )
            """)
            conn.commit()
    except sqlite3.Error as e:
        print(f"[survey_ai_db] init error: {e}")


def insert_survey_response(data_tuple):
    """Insert one row. `data_tuple` must match the column order above (excluding id)."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO survey_responses (
                    name, email,
                    ai_personalized_learning, ai_self_paced_learning,
                    ai_real_time_feedback, ai_confidence_growth,
                    ai_motivation, ai_engagement, ai_clear_explanations,
                    ai_address_challenges, ai_enough_exercises,
                    ai_considers_preferences, ai_no_technical_issues,
                    ai_user_friendly, compare_personalized, compare_engagement,
                    compare_understanding, compare_support, compare_effectiveness,
                    open_likes, open_dislikes, open_improvements, open_personalization,
                    feedback_importance, feedback_traditional_support,
                    feedback_ai_improvement, feedback_recommendation,
                    feedback_preference, feedback_additional
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                data_tuple,
            )
            conn.commit()
    except sqlite3.Error as e:
        print(f"[survey_ai_db] insert error: {e}")


def get_all_responses():
    """Return all survey responses as a DataFrame."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            return pd.read_sql_query("SELECT * FROM survey_responses", conn)
    except sqlite3.Error as e:
        print(f"[survey_ai_db] fetch error: {e}")
        return pd.DataFrame()
