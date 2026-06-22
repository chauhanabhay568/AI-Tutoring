from __future__ import annotations

import logging
from typing import Any

import fitz  # PyMuPDF
import streamlit as st

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)


# ── Text extraction ──────────────────────────────────────────────────────────

def extract_text_from_pdf(uploaded_file: Any) -> str:
    """Extract plain text from an uploaded PDF file."""
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)
    with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
        return "\n".join(page.get_text() for page in doc)


def extract_text_from_txt(uploaded_file: Any) -> str:
    """Decode and return text from an uploaded TXT file."""
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)
    return uploaded_file.read().decode("utf-8").strip()


# ── Chunking ─────────────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=overlap
    )
    return splitter.split_text(text)


# ── ChromaDB ingestion ────────────────────────────────────────────────────────

def ingest_file_to_chroma(
    uploaded_file: Any,
    embedding_model: Any | None,
    chroma_client: Any | None = None,
) -> Any | None:
    """
    Extract text from an uploaded file, chunk it, embed it,
    and store everything in a fresh ChromaDB collection.
    """
    if embedding_model is None:
        logger.warning("Skipping Chroma ingestion because no embedding model is available.")
        return None
    if chroma_client is None:
        raise ValueError("chroma_client is required for Chroma ingestion.")

    file_type = uploaded_file.type
    print(f"[rag_utils] ingest_file_to_chroma: file={getattr(uploaded_file, 'name', '<unknown>')}, type={file_type}")

    if file_type == "application/pdf":
        text = extract_text_from_pdf(uploaded_file)
    elif file_type == "text/plain":
        text = extract_text_from_txt(uploaded_file)
    else:
        raise ValueError("Unsupported file format. Please upload a PDF or TXT file.")

    chunks = chunk_text(text)
    print(f"[rag_utils] extracted {len(chunks)} chunks from {getattr(uploaded_file, 'name', '<unknown>')}")

    for col in chroma_client.list_collections():
        chroma_client.delete_collection(col)

    collection = chroma_client.create_collection("session_documents")
    embeddings = [embedding_model.encode(chunk) for chunk in chunks]

    collection.add(
        ids=[f"doc_{uploaded_file.name}_{i}" for i in range(len(chunks))],
        documents=chunks,
        embeddings=embeddings,
        metadatas=[{"chunk_id": i, "source": uploaded_file.name} for i in range(len(chunks))],
    )
    print(f"[rag_utils] stored {len(chunks)} chunks in Chroma collection 'session_documents'")
    return collection


def retrieve_context(
    query: str,
    embedding_model: Any | None,
    collection: Any | None = None,
    n_results: int = 3,
) -> str:
    """
    Embed a query and return the top-n most relevant chunks
    from the current ChromaDB collection.
    """
    if collection is None:
        try:
            collection = st.session_state.get("collection")
        except Exception:
            collection = None
    if not query or embedding_model is None or collection is None:
        print(
            "[rag_utils] retrieve_context skipped: "
            f"query_present={bool(query)}, embedding_model_present={embedding_model is not None}, "
            f"collection_present={collection is not None}"
        )
        return ""

    try:
        print(f"[rag_utils] retrieve_context running for query length={len(query)} with n_results={n_results}")
        query_embedding = embedding_model.encode(query)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
        )
        chunks = results.get("documents", [[]])[0]
        print(f"[rag_utils] retrieve_context returned {len(chunks)} chunks")
        return "\n\n".join(chunks)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        logger.exception("Context retrieval failed: %s", exc)
        return ""


# ── Prompt building ───────────────────────────────────────────────────────────

def build_system_prompt(student_prefs: dict[str, Any]) -> str:
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

def mark_topic_form_submitted() -> str:
    """Return the session key used by the topic-help form submit logic."""
    return "topic_pref_submitted"
