import io
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


# ── Data helpers ──────────────────────────────────────────────────────────────

def dataframe_to_csv(df):
    """Convert a DataFrame to a CSV string (for download buttons)."""
    output = io.StringIO()
    df.to_csv(output, index=False)
    return output.getvalue()


def student_data_to_dataframe(students_data):
    """
    Flatten the nested student-data structure (one row per subject)
    and return a pandas DataFrame.
    """
    if isinstance(students_data, dict):
        students_data = [students_data]

    rows = []
    for student in students_data:
        for subject in [s.strip() for s in student["subjects"].split(",")]:
            details = student["subject_details"][subject]
            rows.append({
                "email": student["email"],
                "age": student["age"],
                "grade_level": student["grade_level"],
                "preferred_language": student["preferred_language"],
                "subject": subject,
                "understanding_level": details["understanding_level"],
                "past_learning_methods": details["past_learning_methods"],
                "confidence_level": details["confidence_level"],
                "learning_goals": details["learning_goals"],
            })

    return pd.DataFrame(rows)


def validate_subject_data(subject_data):
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

def plot_confidence_gauge(student_row):
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


def plot_confidence_bar(df):
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


def plot_learning_methods_pie(df):
    """Donut chart of past learning methods."""
    return px.pie(df, names="past_learning_methods", hole=0.3)


def display_learning_goals(df):
    """Render learning goals as simple markdown cards."""
    for _, row in df.iterrows():
        st.markdown(f"**Subject:** {row['subject']}  \n**Learning Goal:** {row['learning_goals']}")


# ── Dynamic form helpers ──────────────────────────────────────────────────────

def render_subject_fields(subjects_list):
    """
    Render input widgets for each subject in subjects_list.
    Returns a dict keyed by subject name.
    """
    subject_data = {}
    for subject in subjects_list:
        st.subheader(f"Details for {subject}")
        subject_data[subject] = {
            "understanding_level": st.selectbox(
                f"Level of Understanding for {subject}",
                ["Beginner", "Intermediate", "Advanced"],
                key=f"understanding_{subject}",
            ),
            "past_learning_methods": st.text_area(
                f"Past Learning Methods for {subject}",
                placeholder="e.g. Lectures, Online Courses, Textbooks",
                key=f"methods_{subject}",
            ),
            "confidence_level": st.slider(
                f"Confidence Level for {subject} (1–5)", 1, 5, 3,
                key=f"confidence_{subject}",
            ),
            "learning_goals": st.text_area(
                f"Learning Goals for {subject}",
                placeholder="e.g. master basics, prepare for an exam",
                key=f"goals_{subject}",
            ),
        }
    return subject_data


def render_subject_fields_for_update(student_data):
    """
    Render pre-filled input widgets for updating existing subject data.
    Returns the updated subject_data dict.
    """
    subject_data = student_data.get("subject_details", {})

    for subject, data in subject_data.items():
        st.subheader(f"Update details for {subject}")
        subject_data[subject] = {
            "understanding_level": st.selectbox(
                f"Level of Understanding for {subject}",
                ["Beginner", "Intermediate", "Advanced"],
                index=["Beginner", "Intermediate", "Advanced"].index(
                    data.get("understanding_level", "Intermediate")
                ),
                key=f"understanding_update_{subject}",
            ),
            "past_learning_methods": st.text_area(
                f"Past Learning Methods for {subject}",
                value=data.get("past_learning_methods", ""),
                key=f"methods_update_{subject}",
            ),
            "confidence_level": st.slider(
                f"Confidence Level for {subject} (1–5)", 1, 5,
                data.get("confidence_level", 3),
                key=f"confidence_update_{subject}",
            ),
            "learning_goals": st.text_area(
                f"Learning Goals for {subject}",
                value=data.get("learning_goals", ""),
                key=f"goals_update_{subject}",
            ),
        }

    return subject_data
