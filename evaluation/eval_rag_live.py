from __future__ import annotations

import argparse
import io
import os
import re
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import chromadb
from deepeval.models import GPTModel
from deepeval.test_case import LLMTestCase
from dotenv import dotenv_values, load_dotenv

from evaluation.metrics import build_rag_metrics
from evaluation.models import DatasetValidationError, load_json_list
from evaluation.reporting import summarize, write_reports
from utils.llm_client import EmbeddingClient, LLMClient, build_embedding_client, build_llm_client
from utils.rag_utils import build_system_prompt, chunk_text, extract_text_from_pdf, extract_text_from_txt


DEFAULT_DATASET = PROJECT_ROOT / "evaluation" / "datasets" / "rag_live_cases.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "evaluation" / "results"
DEFAULT_DOCS_DIR = PROJECT_ROOT / "evaluation" / "datasets" / "docs"
DEFAULT_JUDGE_MODEL = "llama-3.3-70b-versatile"
GROQ_API_KEY_NAME = "GROQ_API_KEY"
GROQ_OPENAI_BASE_URL = "https://api.groq.com/openai/v1"
SUPPORTED_SUFFIXES = {".pdf", ".txt"}
LIVE_EVALUATION_TYPE = "rag_live"
MAX_COLLECTION_NAME_LENGTH = 63


@dataclass(frozen=True)
class LiveRagCase:
    case_id: str
    document_path: str
    input: str
    expected_output: str | None = None


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate live RAG responses with DeepEval.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--model", default=os.getenv("DEEPEVAL_JUDGE_MODEL", DEFAULT_JUDGE_MODEL))
    parser.add_argument("--threshold", type=float, default=0.7)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the dataset and document references without generating answers.",
    )
    return parser.parse_args(argv)


def _project_env_values() -> dict[str, str | None]:
    values: dict[str, str | None] = dict(dotenv_values(PROJECT_ROOT / ".env"))
    values.update(os.environ)
    return values


def build_groq_judge_model(
    model_name: str,
    config: Mapping[str, str | None] | None = None,
) -> GPTModel:
    """Build a Groq-backed DeepEval judge with no OpenAI fallback."""
    values = _project_env_values() if config is None else config
    api_key = values.get(GROQ_API_KEY_NAME) or ""
    if not api_key:
        raise ValueError(
            f"Missing required API key: '{GROQ_API_KEY_NAME}' must be set for "
            "DeepEval Groq judge calls. OPENAI_API_KEY is not used as a judge fallback."
        )

    return GPTModel(
        model=model_name,
        api_key=api_key,
        base_url=GROQ_OPENAI_BASE_URL,
        cost_per_input_token=0,
        cost_per_output_token=0,
    )


def _required_text(item: dict[str, Any], field: str, case_id: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise DatasetValidationError(
            f"Case '{case_id}' requires a non-empty string field '{field}'."
        )
    return value.strip()


def load_live_cases(path: Path) -> list[LiveRagCase]:
    cases = []
    for index, item in enumerate(load_json_list(path)):
        case_id = str(item.get("id") or f"live_rag_{index + 1}")
        document_path = _required_text(item, "document_path", case_id)
        expected = item.get("expected_output")
        if expected is not None and (not isinstance(expected, str) or not expected.strip()):
            raise DatasetValidationError(
                f"Case '{case_id}' expected_output must be a non-empty string when set."
            )
        cases.append(
            LiveRagCase(
                case_id=case_id,
                document_path=document_path,
                input=_required_text(item, "input", case_id),
                expected_output=expected.strip() if expected else None,
            )
        )
    return cases


def _resolve_document_path(document_path: str, docs_dir: Path = DEFAULT_DOCS_DIR) -> Path:
    relative = Path(document_path)
    if relative.is_absolute():
        raise DatasetValidationError(
            f"Document path '{document_path}' must be relative to {docs_dir}."
        )
    resolved_docs_dir = docs_dir.resolve()
    resolved = (resolved_docs_dir / relative).resolve()
    if resolved_docs_dir not in resolved.parents and resolved != resolved_docs_dir:
        raise DatasetValidationError(
            f"Document path '{document_path}' must stay under {docs_dir}."
        )
    return resolved


def _as_uploaded_file(path: Path) -> io.BytesIO:
    file_obj = io.BytesIO(path.read_bytes())
    file_obj.name = path.name  # type: ignore[attr-defined]
    file_obj.type = "application/pdf" if path.suffix.lower() == ".pdf" else "text/plain"  # type: ignore[attr-defined]
    file_obj.seek(0)
    return file_obj


def _extract_document_text(path: Path) -> str:
    uploaded_file = _as_uploaded_file(path)
    if path.suffix.lower() == ".pdf":
        return extract_text_from_pdf(uploaded_file)
    if path.suffix.lower() == ".txt":
        return extract_text_from_txt(uploaded_file)
    raise DatasetValidationError(
        f"Unsupported source document '{path.name}'. Only PDF and TXT files are allowed."
    )


def validate_dataset_documents(cases: list[LiveRagCase], docs_dir: Path = DEFAULT_DOCS_DIR) -> None:
    for case in cases:
        document_path = _resolve_document_path(case.document_path, docs_dir)
        if document_path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise DatasetValidationError(
                f"Case '{case.case_id}' references unsupported file type '{document_path.suffix}'."
            )
        if not document_path.exists():
            raise DatasetValidationError(
                f"Case '{case.case_id}' references missing document: {document_path}"
            )


def _build_minimal_student_prefs(case: LiveRagCase) -> dict[str, Any]:
    return {
        "age": "Not Specified",
        "grade_level": "Not Specified",
        "preferred_language": "English",
        "subject": "Python",
        "specific_subtopics": "recursion, list mutability",
        "understanding_level": "Intermediate",
        "past_learning_methods": "Not Specified",
        "confidence_level": 3,
        "learning_goals": f"Answer the question for case {case.case_id} using the provided document.",
        "preferred_level": "Intermediate",
        "assistance_type": "Question Answering",
        "previous_experience": "No",
    }


def _make_collection_name(document_path: Path) -> str:
    # Chroma collection names must be 3-63 chars and use only a restricted charset.
    slug = re.sub(r"[^a-z0-9_-]+", "-", document_path.stem.lower()).strip("-_")
    if not slug:
        slug = "doc"

    suffix = uuid.uuid4().hex[:8]
    prefix = "live-rag"
    available = MAX_COLLECTION_NAME_LENGTH - len(prefix) - len(suffix) - 2
    slug = slug[: max(1, available)].strip("-_")
    if not slug:
        slug = "doc"

    return f"{prefix}-{slug}-{suffix}"


def _ingest_document(
    document_path: Path,
    embedding_model: EmbeddingClient,
    chroma_client: Any,
) -> Any:
    text = _extract_document_text(document_path)
    if not text.strip():
        raise DatasetValidationError(f"Document '{document_path.name}' does not contain readable text.")

    chunks = chunk_text(text)
    if not chunks:
        raise DatasetValidationError(f"Document '{document_path.name}' could not be chunked.")

    collection = chroma_client.create_collection(name=_make_collection_name(document_path))
    embeddings = [embedding_model.encode(chunk) for chunk in chunks]
    collection.add(
        ids=[f"{document_path.stem}_{index}" for index in range(len(chunks))],
        documents=chunks,
        embeddings=embeddings,
        metadatas=[{"chunk_id": index, "source": document_path.name} for index in range(len(chunks))],
    )
    return collection


def retrieve_context_chunks(
    query: str,
    embedding_model: EmbeddingClient,
    collection: Any,
    n_results: int = 3,
) -> list[str]:
    query_embedding = embedding_model.encode(query)
    results = collection.query(query_embeddings=[query_embedding], n_results=n_results)
    documents = results.get("documents", [[]])
    if not documents:
        return []
    chunks = documents[0] or []
    return [chunk for chunk in chunks if isinstance(chunk, str) and chunk.strip()]


def _completion_text(response: Any) -> str:
    if isinstance(response, str):
        return response.strip()
    choices = getattr(response, "choices", None)
    if choices is None and isinstance(response, dict):
        choices = response.get("choices")
    if not choices:
        raise RuntimeError("LLM completion returned no choices.")
    first_choice = choices[0]
    message = getattr(first_choice, "message", None)
    if message is None and isinstance(first_choice, dict):
        message = first_choice.get("message")
    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("LLM completion returned an empty response.")
    return content.strip()


def _measure_case(
    case_id: str,
    test_case: LLMTestCase,
    metrics: list[Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for metric in metrics:
        row = {
            "evaluation_type": LIVE_EVALUATION_TYPE,
            "case_id": case_id,
            "metric": metric.__name__,
            "score": None,
            "threshold": metric.threshold,
            "passed": None,
            "reason": "",
            "error": "",
        }
        try:
            metric.measure(test_case)
            row.update(
                {
                    "score": round(float(metric.score), 4),
                    "passed": bool(metric.is_successful()),
                    "reason": str(metric.reason or ""),
                }
            )
        except Exception as exc:  # pragma: no cover - exercised in failure tests
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
        status = "ERROR" if row["error"] else ("PASS" if row["passed"] else "FAIL")
        score = "n/a" if row["score"] is None else f"{row['score']:.4f}"
        print(f"[{status}] {case_id} | {row['metric']} | {score}")
    return rows


def run_live_case(
    case: LiveRagCase,
    embedding_model: EmbeddingClient,
    llm_client: LLMClient,
    judge_model: Any,
    threshold: float,
    docs_dir: Path = DEFAULT_DOCS_DIR,
) -> list[dict[str, Any]]:
    document_path = _resolve_document_path(case.document_path, docs_dir)
    if document_path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise DatasetValidationError(
            f"Case '{case.case_id}' references unsupported file type '{document_path.suffix}'."
        )
    if not document_path.exists():
        raise DatasetValidationError(f"Case '{case.case_id}' references missing document: {document_path}")

    chroma_client = chromadb.EphemeralClient()
    collection = _ingest_document(document_path, embedding_model, chroma_client)
    retrieval_context = retrieve_context_chunks(case.input, embedding_model, collection, n_results=3)
    system_prompt = build_system_prompt(_build_minimal_student_prefs(case))
    context_text = "\n\n".join(retrieval_context)
    messages = [
        {
            "role": "system",
            "content": system_prompt
            + "\n\nUse the retrieved context to answer the student's question.",
        },
        {
            "role": "user",
            "content": f"Question: {case.input}\n\nRetrieved context:\n{context_text or 'No relevant context was retrieved.'}",
        },
    ]

    response = llm_client.complete(messages)
    actual_output = _completion_text(response)

    test_case = LLMTestCase(
        input=case.input,
        actual_output=actual_output,
        expected_output=case.expected_output,
        retrieval_context=retrieval_context,
    )
    metrics = build_rag_metrics(judge_model, threshold, case.expected_output is not None)
    return _measure_case(case.case_id, test_case, metrics)


def evaluate_live_cases(
    cases: list[LiveRagCase],
    embedding_model: EmbeddingClient,
    llm_client: LLMClient,
    judge_model: Any,
    threshold: float,
    docs_dir: Path = DEFAULT_DOCS_DIR,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        try:
            rows.extend(run_live_case(case, embedding_model, llm_client, judge_model, threshold, docs_dir))
        except Exception as exc:
            rows.append(
                {
                    "evaluation_type": LIVE_EVALUATION_TYPE,
                    "case_id": case.case_id,
                    "metric": "LiveRagExecutionError",
                    "score": None,
                    "threshold": threshold,
                    "passed": None,
                    "reason": "",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            print(
                f"[ERROR] {case.case_id} | LiveRagExecutionError | n/a | "
                f"{type(exc).__name__}: {exc}"
            )
    return rows


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args(argv)
    if not 0 <= args.threshold <= 1:
        print("Error: --threshold must be between 0 and 1.", file=sys.stderr)
        return 2

    try:
        cases = load_live_cases(args.dataset)
        if args.validate_only:
            validate_dataset_documents(cases, DEFAULT_DOCS_DIR)
            print(f"Validated {len(cases)} live case(s).")
            return 0
    except DatasetValidationError as exc:
        print(f"Dataset error: {exc}", file=sys.stderr)
        return 2

    try:
        judge_model = build_groq_judge_model(args.model)
        embedding_model = build_embedding_client()
        llm_client = build_llm_client()
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    rows = evaluate_live_cases(
        cases,
        embedding_model,
        llm_client,
        judge_model,
        args.threshold,
        DEFAULT_DOCS_DIR,
    )
    csv_path, json_path = write_reports(rows, args.output_dir)
    print("\nAggregate results:")
    for metric, values in summarize(rows)["metric_summary"].items():
        print(
            f"- {metric}: mean={values['mean_score']}, "
            f"pass_rate={values['pass_rate']}, errors={values['errors']}"
        )
    print(f"\nDetailed CSV: {csv_path}")
    print(f"Summary JSON: {json_path}")
    return 1 if any(row["error"] for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
