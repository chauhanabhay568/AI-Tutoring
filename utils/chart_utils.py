import io
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils.subject_management import parse_subjects


# ── Data helpers ──────────────────────────────────────────────────────────────

def dataframe_to_csv(df: pd.DataFrame) -> str:
    """Convert a DataFrame to a CSV string (for download buttons)."""
    output = io.StringIO()
    df.to_csv(output, index=False)
    return output.getvalue()


def student_data_to_dataframe(students_data: dict[str, Any] | list[dict[str, Any]]) -> pd.DataFrame:
    """
    Flatten the nested student-data structure (one row per subject)
    and return a pandas DataFrame.
    """
    if isinstance(students_data, dict):
        students_data = [students_data]

    rows = []
    for student in students_data:
        subjects = parse_subjects(student.get("subjects", ""))
        subject_details = student.get("subject_details", {})
        if not subjects or not isinstance(subject_details, dict):
            continue

        for subject in subjects:
            if subject not in subject_details:
                continue
            details = subject_details.get(subject, {})
            if not isinstance(details, dict) or not details:
                continue
            rows.append({
                "email": student.get("email", ""),
                "age": student.get("age", ""),
                "grade_level": student.get("grade_level", ""),
                "preferred_language": student.get("preferred_language", ""),
                "subject": subject,
                "understanding_level": details.get("understanding_level", ""),
                "past_learning_methods": details.get("past_learning_methods", ""),
                "confidence_level": details.get("confidence_level", 0),
                "learning_goals": details.get("learning_goals", ""),
            })

    columns = [
        "email",
        "age",
        "grade_level",
        "preferred_language",
        "subject",
        "understanding_level",
        "past_learning_methods",
        "confidence_level",
        "learning_goals",
    ]
    return pd.DataFrame(rows, columns=columns)


def validate_subject_data(subject_data: dict[str, dict[str, Any]]) -> str | None:
    """
    Check that every field in subject_data is filled in.
    Returns an HTML error string, or None if everything is valid.
    """
    errors = []
    for subject, data in subject_data.items():
        for field, value in data.items():
            if not value or str(value).strip() == "":
                errors.append(f"Field '{field}' for subject '{subject}' is required.")
    return "<br>".join(errors) if errors else None


# ── Chart builders ────────────────────────────────────────────────────────────

def plot_confidence_gauge(student_row: pd.Series) -> go.Figure:
    """Gauge chart showing confidence level for a single subject."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=student_row["confidence_level"],
        title={"text": f"Confidence in {student_row['subject']}"},
        gauge={
            "axis": {"range": [0, 5]},
            "bar": {"color": "blue"},
            "steps": [
                {"range": [0, 2], "color": "red"},
                {"range": [2, 4], "color": "yellow"},
                {"range": [4, 5], "color": "green"},
            ],
        },
    ))
    return fig


def plot_confidence_bar(df: pd.DataFrame) -> go.Figure:
    """Grouped bar chart: confidence level per subject, coloured by understanding level."""
    fig = px.bar(
        df,
        x="subject",
        y="confidence_level",
        color="understanding_level",
        text="confidence_level",
        barmode="group",
    )
    fig.update_traces(texttemplate="%{text}", textposition="outside")
    fig.update_layout(xaxis_title="Subject", yaxis_title="Confidence Level")
    return fig


def plot_learning_methods_pie(df: pd.DataFrame) -> go.Figure:
    """Donut chart of past learning methods."""
    return px.pie(df, names="past_learning_methods", hole=0.3)


def display_learning_goals(df: pd.DataFrame) -> None:
    """Render learning goals as simple markdown cards."""
    for _, row in df.iterrows():
        st.markdown(f"**Subject:** {row['subject']}  \n**Learning Goal:** {row['learning_goals']}")


# ── Dynamic form helpers ──────────────────────────────────────────────────────

def render_subject_fields(subjects_list: list[str], key_prefix: str = "") -> dict[str, dict[str, Any]]:
    """
    Render input widgets for each subject in subjects_list.
    Returns a dict keyed by subject name.
    """
    subject_data = {}
    for subject in subjects_list:
        widget_key = f"{key_prefix}{subject}".replace(" ", "_")
        st.subheader(f"Details for {subject}")
        subject_data[subject] = {
            "understanding_level": st.selectbox(
                f"Level of Understanding for {subject}",
                ["Beginner", "Intermediate", "Advanced"],
                key=f"understanding_{widget_key}",
            ),
            "past_learning_methods": st.text_area(
                f"Past Learning Methods for {subject}",
                placeholder="e.g. Lectures, Online Courses, Textbooks",
                key=f"methods_{widget_key}",
            ),
            "confidence_level": st.slider(
                f"Confidence Level for {subject} (1–5)", 1, 5, 3,
                key=f"confidence_{widget_key}",
            ),
            "learning_goals": st.text_area(
                f"Learning Goals for {subject}",
                placeholder="e.g. master basics, prepare for an exam",
                key=f"goals_{widget_key}",
            ),
        }
    return subject_data


def render_subject_fields_for_update(student_data: dict[str, Any], key_prefix: str = "") -> dict[str, dict[str, Any]]:
    """
    Render pre-filled input widgets for updating existing subject data.
    Returns the updated subject_data dict.
    """
    subject_data = dict(student_data.get("subject_details", {}))

    for subject, data in subject_data.items():
        widget_key = f"{key_prefix}{subject}".replace(" ", "_")
        st.subheader(f"Update details for {subject}")
        confidence_levels = ["Beginner", "Intermediate", "Advanced"]
        understanding_level = data.get("understanding_level", "Intermediate")
        if understanding_level not in confidence_levels:
            understanding_level = "Intermediate"

        subject_data[subject] = {
            "understanding_level": st.selectbox(
                f"Level of Understanding for {subject}",
                confidence_levels,
                index=confidence_levels.index(understanding_level),
                key=f"understanding_update_{widget_key}",
            ),
            "past_learning_methods": st.text_area(
                f"Past Learning Methods for {subject}",
                value=data.get("past_learning_methods", ""),
                key=f"methods_update_{widget_key}",
            ),
            "confidence_level": st.slider(
                f"Confidence Level for {subject} (1–5)", 1, 5,
                data.get("confidence_level", 3),
                key=f"confidence_update_{widget_key}",
            ),
            "learning_goals": st.text_area(
                f"Learning Goals for {subject}",
                value=data.get("learning_goals", ""),
                key=f"goals_update_{widget_key}",
            ),
        }

    return subject_data
