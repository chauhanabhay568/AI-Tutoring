import streamlit as st
from navigation import make_sidebar
from database.student_db import get_student_by_email
from database.survey_traditional_db import (
    init_survey_traditional_db,
    insert_survey_response,
    get_all_responses,
)
from utils.css_utils import load_css
from utils.chart_utils import dataframe_to_csv

make_sidebar()
load_css("styles/style.css")
init_survey_traditional_db()

email = st.session_state.get("user_email")
name  = st.session_state.get("user_name")

# ── Admin view ────────────────────────────────────────────────────────────────
if email == "admin.com" and name == "admin":
    st.header("Survey Results — Traditional Teaching")
    df  = get_all_responses()
    st.dataframe(df.head())
    st.download_button("📥 Download CSV", dataframe_to_csv(df),
                       "survey_traditional.csv", "text/csv")
    st.stop()

# ── Student guard ─────────────────────────────────────────────────────────────
if not get_student_by_email(email):
    st.error("Please complete your profile in My Account before filling in the survey.")
    st.stop()

# ── Survey ────────────────────────────────────────────────────────────────────
st.header("Survey — Traditional Teaching Methods")
st.write("Thank you for participating! Please answer the questions below.")

st.subheader("1. Demographic Information")
course             = st.radio("Enrolment level", ["Undergraduate", "Postgraduate"])
general_proficiency = st.radio("General programming proficiency", ["None", "Low", "Medium", "High"])
python_proficiency  = st.radio("Python proficiency", ["None", "Low", "Medium", "High"])

st.subheader("2. Experience with Traditional Teaching")
teaching_methods = st.multiselect(
    "How are you taught programming? (select all that apply)",
    ["Lectures", "Textbooks", "VLE", "In-lab exercises",
     "Group discussions", "Online videos", "Pre-recorded lectures"],
)
effective_learning = st.radio("Are you learning effectively with traditional methods?", ["Yes", "No"])
satisfaction = st.radio(
    "Overall satisfaction with traditional teaching:",
    ["Highly Unsatisfied", "Unsatisfied", "Neutral", "Satisfied", "Highly Satisfied"],
)

st.subheader("3. Attitudes Towards Personalised Learning")
st.write("Rate each statement from **1 (Strongly Disagree)** to **7 (Strongly Agree)**.")

likert_questions = [
    "Traditional teaching allows for personalised learning tailored to my needs.",
    "I am able to learn at my own pace in traditional teaching.",
    "I receive real-time personalised feedback through traditional teaching.",
    "My confidence grows as I complete learning in traditional teaching.",
    "I am motivated when learning through traditional teaching.",
    "I am highly engaged when learning through traditional teaching.",
    "Explanations for my mistakes are clear in traditional teaching.",
    "My specific challenges are effectively addressed in traditional teaching.",
    "Enough exercises are provided to enhance my skills.",
    "My learning preferences are considered in traditional teaching.",
]

responses = {q: st.slider(q, 1, 7, 4) for q in likert_questions}

if st.button("Submit Survey"):
    payload = {
        "Name": name, "Email": email,
        "Course Level": course,
        "General Proficiency": general_proficiency,
        "Python Proficiency": python_proficiency,
        "Teaching Methods": ", ".join(teaching_methods),
        "Effective Learning": effective_learning,
        "Satisfaction": satisfaction,
        **responses,
    }
    insert_survey_response(payload)
    st.success("Thank you! Your responses have been recorded.")
