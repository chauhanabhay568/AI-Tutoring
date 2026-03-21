import streamlit as st
from navigation import make_sidebar
from database.student_db import get_student_by_email
from database.survey_ai_db import (
    init_survey_ai_db,
    insert_survey_response,
    get_all_responses,
)
from utils.css_utils import load_css
from utils.chart_utils import dataframe_to_csv

make_sidebar()
load_css("styles/style.css")
init_survey_ai_db()

email = st.session_state.get("user_email")
name  = st.session_state.get("user_name")

# ── Admin view ────────────────────────────────────────────────────────────────
if email == "admin.com" and name == "admin":
    st.header("Survey Results — AI Tutoring")
    df = get_all_responses()
    st.dataframe(df.head())
    st.download_button("📥 Download CSV", dataframe_to_csv(df),
                       "survey_ai.csv", "text/csv")
    st.stop()

# ── Student guard ─────────────────────────────────────────────────────────────
if not get_student_by_email(email):
    st.error("Please complete your profile in My Account before filling in the survey.")
    st.stop()

# ── Likert scale helper ───────────────────────────────────────────────────────
OPTIONS = {
    "Strongly Agree": 1, "Agree": 2, "Lightly Agree": 3,
    "Neutral": 4,
    "Lightly Disagree": 5, "Disagree": 6, "Strongly Disagree": 7,
}

def likert(label):
    return st.radio(label, list(OPTIONS.keys()), key=label)

# ── Survey ────────────────────────────────────────────────────────────────────
st.header("Survey — AI Tutoring System")
st.write("Thank you for participating in this survey about AI Tutoring Systems.")

st.subheader("1. AI Tutoring System Experience")
ai_personalized    = likert("The AI Tutoring System allows for personalised learning tailored to my needs.")
ai_self_paced      = likert("I am able to learn at my own pace in the AI Tutoring System.")
ai_feedback        = likert("I receive real-time personalised feedback from the AI Tutoring System.")
ai_confidence      = likert("My confidence grows when using the AI Tutoring System.")
ai_motivation      = likert("I am more motivated when learning with the AI Tutoring System.")
ai_engagement      = likert("I am highly engaged when learning with the AI Tutoring System.")
ai_explanations    = likert("The AI Tutoring System provides clear explanations for my mistakes.")
ai_challenges      = likert("The AI Tutoring System effectively addresses my challenges.")
ai_exercises       = likert("The AI Tutoring System provides enough practice exercises.")
ai_preferences     = likert("The AI Tutoring System considers my learning preferences.")
ai_no_issues       = likert("There are no technical issues in the AI Tutoring System.")
ai_user_friendly   = likert("The AI Tutoring System is user-friendly.")

st.subheader("2. AI vs Traditional Teaching")
cmp_personalized   = likert("AI provides a more personalised learning experience than traditional methods.")
cmp_engagement     = likert("My engagement is higher with the AI Tutoring System.")
cmp_understanding  = likert("I understand concepts more easily through the AI Tutoring System.")
cmp_support        = likert("AI provides more learning support than traditional methods.")
cmp_effectiveness  = likert("I learn more effectively with AI than with traditional methods.")

st.subheader("3. Open-Ended Questions")
open_likes         = st.text_area("What did you like most about the AI Tutoring System?")
open_dislikes      = st.text_area("What did you like least?")
open_improvements  = st.text_area("What improvements are needed?")
open_personal      = st.text_area("How personalised did the AI experience feel? Why?")

st.subheader("4. Additional Feedback")
fb_importance      = st.text_area("How important is personalised learning for programming?")
fb_trad_support    = st.text_area("Is personalised learning fully supported in traditional teaching?")
fb_ai_improve      = st.text_area("Can AI improve personalised learning?")
fb_recommend       = st.text_area("Would you recommend AI Tutoring Systems?")
fb_preference      = st.text_area("Do you prefer AI tutoring or traditional methods?")
fb_additional      = st.text_area("Any additional comments?")

if st.button("Submit Survey"):
    row = (
        name, email,
        OPTIONS[ai_personalized], OPTIONS[ai_self_paced], OPTIONS[ai_feedback],
        OPTIONS[ai_confidence], OPTIONS[ai_motivation], OPTIONS[ai_engagement],
        OPTIONS[ai_explanations], OPTIONS[ai_challenges], OPTIONS[ai_exercises],
        OPTIONS[ai_preferences], OPTIONS[ai_no_issues], OPTIONS[ai_user_friendly],
        OPTIONS[cmp_personalized], OPTIONS[cmp_engagement], OPTIONS[cmp_understanding],
        OPTIONS[cmp_support], OPTIONS[cmp_effectiveness],
        open_likes, open_dislikes, open_improvements, open_personal,
        fb_importance, fb_trad_support, fb_ai_improve,
        fb_recommend, fb_preference, fb_additional,
    )
    insert_survey_response(row)
    st.success("Thank you! Your responses have been recorded.")
