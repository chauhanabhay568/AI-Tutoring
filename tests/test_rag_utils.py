from io import BytesIO

from utils.rag_utils import build_system_prompt, chunk_text, extract_text_from_txt, retrieve_context


def test_extract_text_from_txt_decodes_and_strips_upload_content():
    uploaded_file = BytesIO(b"  Photosynthesis stores energy in glucose.  \n")

    assert extract_text_from_txt(uploaded_file) == "Photosynthesis stores energy in glucose."


def test_chunk_text_splits_long_text_with_overlap():
    chunks = chunk_text("alpha beta gamma delta epsilon zeta", chunk_size=18, overlap=5)

    assert len(chunks) > 1
    assert all(chunk.strip() for chunk in chunks)


def test_build_system_prompt_uses_defaults_for_missing_preferences():
    prompt = build_system_prompt({"subject": "Biology", "confidence_level": 3})

    assert "Subject: Biology" in prompt
    assert "Confidence Level: 3/5" in prompt
    assert "Grade Level: Not Specified" in prompt


def test_retrieve_context_returns_empty_string_without_collection(monkeypatch):
    class EmptySessionState(dict):
        pass

    import utils.rag_utils as rag_utils

    monkeypatch.setattr(rag_utils.st, "session_state", EmptySessionState())

    assert retrieve_context("What is mitosis?", embedding_model=object()) == ""


def test_retrieve_context_joins_returned_documents(monkeypatch):
    class FakeEmbedding(list):
        def tolist(self):
            return list(self)

    class FakeEmbeddingModelWithToList:
        def encode(self, query):
            return FakeEmbedding([0.1, 0.2])

    class FakeCollection:
        def query(self, query_embeddings, n_results):
            assert query_embeddings == [[0.1, 0.2]]
            assert n_results == 2
            return {"documents": [["chunk one", "chunk two"]]}

    class FakeSessionState(dict):
        def __getattr__(self, name):
            return self[name]

    import utils.rag_utils as rag_utils

    monkeypatch.setattr(rag_utils.st, "session_state", FakeSessionState(collection=FakeCollection()))

    assert retrieve_context("What is mitosis?", FakeEmbeddingModelWithToList(), n_results=2) == (
        "chunk one\n\nchunk two"
    )
