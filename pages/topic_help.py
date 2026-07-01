import certifi
import os

os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
os.environ.setdefault("SSL_CERT_FILE", certifi.where())

import chromadb
import streamlit as st
from chromadb.config import Settings

from database.student_db import get_student_by_email
from navigation import make_sidebar
from utils.css_utils import load_css
from utils.llm_client import build_embedding_client, build_llm_client
from utils.rag_utils import build_system_prompt, ingest_file_to_chroma, retrieve_context
from utils.subject_management import get_subject_list

# ── Cached resources ──────────────────────────────────────────────────────────
# @st.cache_resource ensures the embedding client (and any lazily-loaded
# sentence-transformers fallback model) is constructed only once per session.
@st.cache_resource
def load_embedding_model():
    return build_embedding_client()


@st.cache_resource
def load_llm():
    return build_llm_client()


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

subjects = get_subject_list(student)
if not subjects:
    st.info("No subjects have been saved yet. Please add at least one subject in My Account before using Topic Help.")
    st.stop()

# ── Preference form ───────────────────────────────────────────────────────────
st.header("Topic Assistance")
st.write("Fill in the details below to get personalised help.")

with st.form("topic_form"):
    st.info("Please fill out all fields.")
    col1, col2, col3 = st.columns([1, 2, 2])

    with col1:
        subject = st.selectbox("Subject", subjects)
    with col2:
        preferred_depth = st.selectbox("Depth of Coverage", ["Beginner", "Intermediate", "Advanced"])
    with col3:
        assistance_type = st.multiselect(
            "Type of Assistance",
            ["Clarification", "Problem-Solving", "Practice Material", "Resources"],
        )

    col4, col5 = st.columns(2)
    with col4:
        specific_subtopics = st.text_area(
            "Specific Subtopics",
            placeholder="e.g. recursion, sorting",
            max_chars=1000,
        )
    with col5:
        previous_experience = st.radio("Previous Experience?", ["No", "Yes", "Partially"])

    uploaded_file = st.file_uploader("Upload reference document (optional)", type=["pdf", "txt"])
    submitted = st.form_submit_button("Submit")

if submitted:
    if len(specific_subtopics) > 1000:
        st.error("Specific subtopics must be 1000 characters or fewer.")
    else:
        st.session_state.topic_pref_submitted = True
        st.session_state.messages = []
        st.session_state.pop("collection", None)

        if previous_experience == "Yes" and uploaded_file:
            if embedding_model is None:
                st.info("Document retrieval is unavailable right now, so your chat will continue without uploaded context.")
            else:
                try:
                    collection = ingest_file_to_chroma(
                        uploaded_file,
                        embedding_model,
                        st.session_state.chroma_client,
                        llm_client=llm,
                    )
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    if collection is not None:
                        st.session_state.collection = collection

# ── Chat ──────────────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

llm = load_llm()

if st.session_state.get("topic_pref_submitted"):
    subject_details_map = student.get("subject_details", {})
    if not isinstance(subject_details_map, dict):
        subject_details_map = {}
    subject_details = subject_details_map.get(subject, {})

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

    system_prompt = build_system_prompt(student_prefs)

    # Render chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask me anything…", max_chars=1000):
        if len(prompt) > 1000:
            st.error("Messages must be 1000 characters or fewer.")
        else:
            context = ""
            if previous_experience == "Yes" and st.session_state.get("collection") is not None:
                context = retrieve_context(
                    prompt,
                    embedding_model,
                    st.session_state.get("collection"),
                )

            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                history = [{"role": "system", "content": system_prompt}]
                # Prior turns (exclude the current user message already appended above)
                history += [{"role": m["role"], "content": m["content"]}
                            for m in st.session_state.messages[:-1][-4:]]
                # Current user message: context injected here so the model
                # attributes it to the question being asked, not global background
                current_content = (
                    f"{prompt}\n\n[Context from your document]\n{context}"
                    if context else prompt
                )
                history.append({"role": "user", "content": current_content})

                try:
                    stream = llm.stream(history)
                    response = st.write_stream(stream)
                except Exception:
                    response = "Sorry, I couldn't generate a response. Please try again."
                    st.markdown(response)

            st.session_state.messages.append({"role": "assistant", "content": response})
