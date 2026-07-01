from __future__ import annotations

import logging
from typing import Any

import fitz  # PyMuPDF
import streamlit as st
from rank_bm25 import BM25Okapi

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

_cross_encoder = None
# BM25 cache: keyed by id(collection) → (corpus_docs, BM25Okapi index)
_bm25_cache: dict[int, tuple[list[str], BM25Okapi]] = {}

_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "be", "as", "so", "we", "he",
    "she", "they", "this", "that", "are", "was", "were", "been", "have",
    "has", "had", "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "can", "not", "no", "nor", "yet", "both", "either",
    "neither", "what", "which", "who", "whom", "whose",
})


def _get_cross_encoder() -> Any:
    global _cross_encoder
    if _cross_encoder is None:
        from sentence_transformers import CrossEncoder
        _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _cross_encoder


def _tokenize(text: str) -> list[str]:
    return [t for t in text.lower().split() if t not in _STOPWORDS and len(t) > 1]


def _get_bm25(collection: Any) -> tuple[list[str], BM25Okapi]:
    """Return (all_docs, BM25Okapi) for a collection, building and caching on first call."""
    col_id = id(collection)
    if col_id not in _bm25_cache:
        all_docs: list[str] = collection.get(include=["documents"]).get("documents") or []
        tokenized = [_tokenize(doc) for doc in all_docs]
        _bm25_cache[col_id] = (all_docs, BM25Okapi(tokenized))
    return _bm25_cache[col_id]


# ── Text extraction ──────────────────────────────────────────────────────────

def _table_to_markdown(table: Any) -> str:
    """Convert a PyMuPDF Table to a markdown string, with fallback for older versions."""
    try:
        return table.to_markdown()
    except Exception:
        rows = table.extract()
        if not rows:
            return ""
        header = [str(c or "").strip() for c in rows[0]]
        lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join("---" for _ in header) + " |",
        ]
        for row in rows[1:]:
            lines.append("| " + " | ".join(str(c or "").strip() for c in row) + " |")
        return "\n".join(lines)


_MIN_IMAGE_PX = 100  # images smaller than this in either dimension are skipped (icons/decorations)


def extract_text_from_pdf(uploaded_file: Any, llm_client: Any | None = None) -> str:
    """
    Extract text from a PDF, preserving table structure as markdown and
    optionally captioning images with a vision LLM.

    For each page:
    1. Detects tables via PyMuPDF find_tables() and converts them to markdown.
    2. Extracts plain-text blocks, skipping regions already captured as tables.
    3. If llm_client is provided, extracts embedded images, captions each one
       via the vision model, and inserts the caption at the image's page position.
    4. Merges all parts in top-to-bottom reading order.
    """
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)

    pages: list[str] = []
    with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
        for page in doc:
            parts: list[tuple[float, str]] = []
            table_rects: list[Any] = []

            # 1. Tables
            try:
                for table in page.find_tables():
                    md = _table_to_markdown(table)
                    if md.strip():
                        bbox = table.bbox
                        parts.append((bbox[1], md))
                        table_rects.append(fitz.Rect(bbox))
            except Exception:
                pass

            # 2. Plain-text blocks outside table regions
            for block in page.get_text("blocks"):
                if block[6] != 0:  # 0=text, 1=image
                    continue
                x0, y0, x1, y1, text = block[:5]
                if not text.strip():
                    continue
                block_rect = fitz.Rect(x0, y0, x1, y1)
                if any(not (block_rect & tr).is_empty for tr in table_rects):
                    continue
                parts.append((y0, text.strip()))

            # 3. Images — caption via vision model when llm_client is provided
            if llm_client is not None:
                seen_xrefs: set[int] = set()
                for img_info in page.get_images(full=False):
                    xref = img_info[0]
                    if xref in seen_xrefs:
                        continue
                    seen_xrefs.add(xref)

                    rects = page.get_image_rects(xref)
                    if not rects:
                        continue
                    rect = rects[0]
                    if rect.width < _MIN_IMAGE_PX or rect.height < _MIN_IMAGE_PX:
                        continue  # skip icons / decorative images
                    if any(not (rect & tr).is_empty for tr in table_rects):
                        continue  # image is part of a table cell — already captured

                    try:
                        pix = fitz.Pixmap(doc, xref)
                        if pix.n - pix.alpha >= 4:  # CMYK → RGB
                            pix = fitz.Pixmap(fitz.csRGB, pix)
                        caption = llm_client.caption_image(pix.tobytes("png"))
                        parts.append((rect.y0, f"[Figure: {caption}]"))
                        logger.info("Captioned image xref=%d on page %d", xref, page.number + 1)
                    except Exception as exc:
                        logger.warning("Image captioning skipped (xref=%d): %s", xref, exc)

            parts.sort(key=lambda p: p[0])
            page_text = "\n\n".join(p[1] for p in parts)
            if page_text.strip():
                pages.append(page_text)

    return "\n\n".join(pages)


def extract_text_from_txt(uploaded_file: Any) -> str:
    """Decode and return text from an uploaded TXT file."""
    if hasattr(uploaded_file, "seek"):
        uploaded_file.seek(0)
    return uploaded_file.read().decode("utf-8").strip()


# ── Chunking ─────────────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150) -> list[str]:
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
    llm_client: Any | None = None,
) -> Any | None:
    """
    Extract text from an uploaded file, chunk it, embed it,
    and store everything in a fresh ChromaDB collection.

    When llm_client is provided, embedded PDF images are captioned by the
    vision model and their descriptions are included in the indexed text.
    """
    if embedding_model is None:
        logger.warning("Skipping Chroma ingestion because no embedding model is available.")
        return None
    if chroma_client is None:
        raise ValueError("chroma_client is required for Chroma ingestion.")

    file_type = uploaded_file.type

    if file_type == "application/pdf":
        text = extract_text_from_pdf(uploaded_file, llm_client=llm_client)
    elif file_type == "text/plain":
        text = extract_text_from_txt(uploaded_file)
    else:
        raise ValueError("Unsupported file format. Please upload a PDF or TXT file.")

    chunks = chunk_text(text)
    
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
    return collection


def retrieve_context_chunks(
    query: str,
    embedding_model: Any | None,
    collection: Any | None = None,
    n_results: int = 5,
    candidate_k: int = 15,
) -> list[str]:
    """
    Hybrid BM25 + dense retrieval with cross-encoder reranking.

    1. Dense: top-candidate_k chunks by embedding similarity.
    2. BM25:  top-candidate_k chunks by keyword score over all stored chunks.
    3. RRF:   reciprocal rank fusion over the union of both candidate sets.
    4. Rerank: cross-encoder scores the fused list; top n_results returned.
    """
    if not query or embedding_model is None or collection is None:
        return []

    try:
        # BM25 corpus — built once per collection object, then cached
        all_docs, bm25 = _get_bm25(collection)
        if not all_docs:
            return []

        n_cand = min(candidate_k, len(all_docs))

        # 1. Dense retrieval
        query_vec = embedding_model.encode(query)
        dense_results = collection.query(query_embeddings=[query_vec], n_results=n_cand)
        dense_chunks: list[str] = dense_results.get("documents", [[]])[0]
        dense_rank: dict[str, int] = {c: r for r, c in enumerate(dense_chunks)}

        # 2. BM25 retrieval (index already built)
        bm25_scores = bm25.get_scores(_tokenize(query))
        top_bm25_idx = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:n_cand]
        bm25_rank: dict[str, int] = {all_docs[i]: r for r, i in enumerate(top_bm25_idx)}

        # 3. Reciprocal Rank Fusion (k=60 is standard)
        candidates = list(set(dense_chunks) | {all_docs[i] for i in top_bm25_idx})
        rrf_k = 60

        def _rrf(chunk: str) -> float:
            return 1.0 / (rrf_k + dense_rank.get(chunk, n_cand)) + \
                   1.0 / (rrf_k + bm25_rank.get(chunk, n_cand))

        candidates.sort(key=_rrf, reverse=True)
        candidates = candidates[: candidate_k * 2]  # cap before reranking

        # 4. Cross-encoder rerank
        reranker = _get_cross_encoder()
        scores = reranker.predict([[query, c] for c in candidates])
        reranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)

        return [chunk for chunk, _ in reranked[:n_results]]

    except Exception as exc:
        logger.exception("Hybrid retrieval failed: %s", exc)
        return []


def retrieve_context(
    query: str,
    embedding_model: Any | None,
    collection: Any | None = None,
    n_results: int = 5,
) -> str:
    """Return retrieved chunks as a single string for injection into the LLM prompt."""
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
    chunks = retrieve_context_chunks(query, embedding_model, collection, n_results)
    return "\n\n".join(chunks)


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
