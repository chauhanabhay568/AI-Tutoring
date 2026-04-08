import os
import streamlit as st
import chromadb
from chromadb.config import Settings
from dotenv import dotenv_values
from openai import OpenAI
from sentence_transformers import SentenceTransformer

from navigation import make_sidebar
from database.student_db import get_student_by_email
from utils.css_utils import load_css
from utils.rag_utils import (
    ingest_file_to_chroma,
    retrieve_context,
    build_system_prompt,
    mark_topic_form_submitted,
)

# ── Config ────────────────────────────────────────────────────────────────────
config = dotenv_values()
os.environ["OPENAI_API_KEY"] = config.get("OPENAI_API_KEY", "")

# ── Cached resources ──────────────────────────────────────────────────────────
@st.cache_resource
def load_embedding_model():
    return SentenceTransformer("all-MiniLM-L6-v2")

@st.cache_resource
def load_llm():
    return OpenAI(api_key=config.get("OPENAI_API_KEY", ""))

# ── ChromaDB (one client per session) ────────────────────────────────────────
if "chroma_client" not in st.session_state:
    st.session_state.chroma_client = chromadb.PersistentClient(
        path="doc_db", settings=Settings()
    )

# ── Load embedding model only when logged in ─────────────────────────────────
embedding_model = None
if st.session_state.get("logged_in"):
    with st.spinner("Loading model…"):
        embedding_model = load_embedding_model()

make_sidebar()
load_css("styles/style.css")

# ── Guard ─────────────────────────────────────────────────────────────────────
email = st.session_state.get("user_email")
student = get_student_by_email(email)

if not student:
    st.error("Please complete your profile in My Account before using Topic Help.")
    st.stop()

# ── Preference form ───────────────────────────────────────────────────────────
st.header("Topic Assistance")
st.write("Fill in the details below to get personalised help.")

with st.form("topic_form"):
    st.info("Please fill out all fields.")
    col1, col2, col3 = st.columns([1, 2, 2])

    with col1:
        subject = st.selectbox("Subject", [s.strip() for s in student["subjects"].split(",")])
    with col2:
        preferred_depth = st.selectbox("Depth of Coverage", ["Beginner", "Intermediate", "Advanced"])
    with col3:
        assistance_type = st.multiselect(
            "Type of Assistance",
            ["Clarification", "Problem-Solving", "Practice Material", "Resources"],
        )

    col4, col5 = st.columns(2)
    with col4:
        specific_subtopics = st.text_area("Specific Subtopics", placeholder="e.g. recursion, sorting")
    with col5:
        previous_experience = st.radio("Previous Experience?", ["No", "Yes", "Partially"])

    uploaded_file = st.file_uploader("Upload reference document (optional)", type=["pdf", "txt"])
    st.form_submit_button("Submit", on_click=mark_topic_form_submitted)

# ── Chat ──────────────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

llm = load_llm()

if st.session_state.get("topic_pref_submitted"):
    subject_details = student["subject_details"].get(subject, {})

    student_prefs = {
        "age": student.get("age"),
        "grade_level": student.get("grade_level"),
        "preferred_language": student.get("preferred_language"),
        "subject": subject,
        "understanding_level": subject_details.get("understanding_level"),
        "past_learning_methods": subject_details.get("past_learning_methods"),
        "confidence_level": subject_details.get("confidence_level"),
        "learning_goals": subject_details.get("learning_goals"),
        "specific_subtopics": specific_subtopics,
        "preferred_level": preferred_depth,
        "assistance_type": ", ".join(assistance_type),
        "previous_experience": previous_experience,
    }

    # Ingest uploaded file once
    if previous_experience == "Yes" and uploaded_file:
        with st.spinner("Processing document…"):
            ingest_file_to_chroma(uploaded_file, embedding_model)

    system_prompt = build_system_prompt(student_prefs)

    # Render chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask me anything…"):
        context = ""
        if previous_experience == "Yes" and uploaded_file:
            context = retrieve_context(prompt, embedding_model)

        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            full_prompt = system_prompt + (f"\n\nContext:\n{context}" if context else "")
            history = [{"role": "system", "content": full_prompt}]
            history += [{"role": m["role"], "content": m["content"]}
                        for m in st.session_state.messages[-5:]]

            stream = llm.chat.completions.create(
                model="gpt-3.5-turbo", messages=history, stream=True
            )
            response = st.write_stream(stream)

        st.session_state.messages.append({"role": "assistant", "content": response})
