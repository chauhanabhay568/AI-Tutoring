import streamlit as st
import fitz  # PyMuPDF

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter


# ── Text extraction ──────────────────────────────────────────────────────────

def extract_text_from_pdf(uploaded_file):
    """Extract plain text from an uploaded PDF file."""
    with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)


def extract_text_from_txt(uploaded_file):
    """Decode and return text from an uploaded TXT file."""
    return uploaded_file.read().decode("utf-8").strip()


# ── Chunking ─────────────────────────────────────────────────────────────────

def chunk_text(text, chunk_size=500, overlap=50):
    """Split text into overlapping chunks."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=overlap
    )
    return splitter.split_text(text)


# ── ChromaDB ingestion ────────────────────────────────────────────────────────

def ingest_file_to_chroma(uploaded_file, embedding_model):
    """
    Extract text from an uploaded file, chunk it, embed it,
    and store everything in a fresh ChromaDB collection.
    """
    file_type = uploaded_file.type

    if file_type == "application/pdf":
        text = extract_text_from_pdf(uploaded_file)
    elif file_type == "text/plain":
        text = extract_text_from_txt(uploaded_file)
    else:
        st.error("Unsupported file format. Please upload a PDF or TXT file.")
        return

    chunks = chunk_text(text)

    # Clear old collections before creating a new one
    for col in st.session_state.chroma_client.list_collections():
        st.session_state.chroma_client.delete_collection(col)

    collection = st.session_state.chroma_client.create_collection("session_documents")
    embeddings = [embedding_model.encode(chunk).tolist() for chunk in chunks]

    collection.add(
        ids=[f"doc_{uploaded_file.name}_{i}" for i in range(len(chunks))],
        documents=chunks,
        embeddings=embeddings,
        metadatas=[{"chunk_id": i, "source": uploaded_file.name} for i in range(len(chunks))],
    )

    st.session_state.collection = collection


def retrieve_context(query, embedding_model, n_results=3):
    """
    Embed a query and return the top-n most relevant chunks
    from the current ChromaDB collection.
    """
    if "collection" not in st.session_state:
        return ""

    query_embedding = embedding_model.encode(query).tolist()
    results = st.session_state.collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
    )
    chunks = results.get("documents", [[]])[0]
    return "\n\n".join(chunks)


# ── Prompt building ───────────────────────────────────────────────────────────

def build_system_prompt(student_prefs):
    """
    Build a personalised system prompt from the student's preferences
    and the topic-help form data.
    """
    template = """
You are a personalized learning assistant designed to support students in their educational journey.
Your goal is to help the student learn effectively based on their preferences and goals.

Student Details:
- Age: {age}
- Grade Level: {grade_level}
- Preferred Language: {preferred_language}

Topic Preferences (strictly follow these):
- Subject: {subject}
- Specific Subtopics: {specific_subtopics}
- Understanding Level: {understanding_level}
- Past Learning Methods: {past_learning_methods}
- Confidence Level: {confidence_level}/5
- Learning Goals: {learning_goals}
- Preferred Depth: {preferred_level}
- Type of Assistance: {assistance_type}
- Previous Experience: {previous_experience}

Provide responses that are:
- Strictly aligned with the subtopics and learning goals above.
- Tailored to the student's understanding level (Beginner / Intermediate / Advanced).
- Clear, encouraging, and focused on measurable progress.
"""
    return template.format(
        age=student_prefs.get("age", "Not Specified"),
        grade_level=student_prefs.get("grade_level", "Not Specified"),
        preferred_language=student_prefs.get("preferred_language", "Not Specified"),
        subject=student_prefs.get("subject", "Not Specified"),
        specific_subtopics=student_prefs.get("specific_subtopics", "Not Specified"),
        understanding_level=student_prefs.get("understanding_level", "Not Specified"),
        past_learning_methods=student_prefs.get("past_learning_methods", "Not Specified"),
        confidence_level=student_prefs.get("confidence_level", "Not Specified"),
        learning_goals=student_prefs.get("learning_goals", "Not Specified"),
        preferred_level=student_prefs.get("preferred_level", "Not Specified"),
        assistance_type=student_prefs.get("assistance_type", "Not Specified"),
        previous_experience=student_prefs.get("previous_experience", "Not Specified"),
    )


# ── Streamlit helpers ─────────────────────────────────────────────────────────

def mark_topic_form_submitted():
    """Callback for the topic-help form submit button."""
    st.session_state.topic_pref_submitted = True
