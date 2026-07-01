from __future__ import annotations

import base64
import warnings
from typing import Any

import openai
from dotenv import dotenv_values

DEFAULT_EMBEDDING_MODEL = "nomic-embed-text-v1_5"
DEFAULT_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

_CAPTION_PROMPT = (
    "This image is from a student study document. "
    "Describe what it shows in 2-4 sentences. "
    "If it is a chart or graph, explain the data and trends it presents. "
    "If it is a diagram, describe the components and relationships. "
    "If it is a table, summarise the key data. "
    "Be concise and factual."
)

PROVIDER_BASE_URLS: dict[str, str | None] = {
    "groq": "https://api.groq.com/openai/v1",
    "openai": None,
    "together": "https://api.together.xyz/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
}

PROVIDER_KEY_NAMES: dict[str, str] = {
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
    "together": "TOGETHER_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


class LLMClient:
    def __init__(
        self,
        primary: openai.OpenAI,
        model: str,
        fallback: openai.OpenAI | None = None,
        fallback_model: str = "gpt-3.5-turbo",
        vision_model: str = DEFAULT_VISION_MODEL,
    ) -> None:
        self.primary = primary
        self.model = model
        self._fallback = fallback
        self.fallback_model = fallback_model
        self.vision_model = vision_model

    def complete(self, messages: list[dict], **kwargs) -> Any:
        """Non-streaming completion with automatic OpenAI fallback on provider error."""
        try:
            return self.primary.chat.completions.create(
                model=self.model, messages=messages, **kwargs
            )
        except openai.APIError:
            if self._fallback is None:
                raise
            return self._fallback.chat.completions.create(
                model=self.fallback_model, messages=messages, **kwargs
            )

    def stream(self, messages: list[dict], **kwargs) -> Any:
        """Streaming completion against the primary provider. Caller handles errors."""
        return self.primary.chat.completions.create(
            model=self.model, messages=messages, stream=True, **kwargs
        )

    def caption_image(self, image_bytes: bytes) -> str:
        """
        Send image bytes to the vision model and return a text caption.
        Uses the same primary client (same provider/key) with self.vision_model.
        """
        b64 = base64.b64encode(image_bytes).decode()
        response = self.primary.chat.completions.create(
            model=self.vision_model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    {"type": "text", "text": _CAPTION_PROMPT},
                ],
            }],
            max_tokens=200,
        )
        return response.choices[0].message.content.strip()


def build_llm_client(config: dict | None = None) -> LLMClient:
    """
    Build an LLMClient from .env configuration.
    Raises ValueError at startup if the primary provider API key is absent.
    """
    if config is None:
        config = dotenv_values()

    provider = config.get("LLM_PROVIDER") or ""
    model = config.get("LLM_MODEL") or ""

    if not provider:
        warnings.warn(
            "LLM_PROVIDER not set in .env — defaulting to 'groq'",
            stacklevel=2,
        )
        provider = "groq"
    if not model:
        warnings.warn(
            "LLM_MODEL not set in .env — defaulting to 'llama-3.3-70b-versatile'",
            stacklevel=2,
        )
        model = "llama-3.3-70b-versatile"

    key_name = PROVIDER_KEY_NAMES.get(provider, f"{provider.upper()}_API_KEY")
    api_key = config.get(key_name) or ""

    if not api_key:
        raise ValueError(
            f"Missing required API key: '{key_name}' must be set in .env for provider "
            f"'{provider}'. Get a free Groq key at https://console.groq.com"
        )

    client_kwargs: dict = {"api_key": api_key}
    base_url = PROVIDER_BASE_URLS.get(provider)
    if base_url:
        client_kwargs["base_url"] = base_url
    primary = openai.OpenAI(**client_kwargs)

    fallback: openai.OpenAI | None = None
    fallback_model = config.get("OPENAI_FALLBACK_MODEL") or "gpt-3.5-turbo"
    openai_key = config.get("OPENAI_API_KEY") or ""
    if openai_key and provider != "openai":
        fallback = openai.OpenAI(api_key=openai_key)

    vision_model = config.get("VISION_MODEL") or DEFAULT_VISION_MODEL
    return LLMClient(primary, model, fallback, fallback_model, vision_model)


def build_quiz_llm_client(config: dict | None = None) -> LLMClient:
    """
    Build an LLMClient for quiz/feedback tasks using QUIZ_MODEL env var.
    Falls back to the chat model if QUIZ_MODEL is not set.
    Same provider and API key as the main client.
    """
    if config is None:
        config = dotenv_values()

    quiz_model = config.get("QUIZ_MODEL") or ""
    if not quiz_model:
        return build_llm_client(config)

    quiz_config = dict(config)
    quiz_config["LLM_MODEL"] = quiz_model
    return build_llm_client(quiz_config)


class EmbeddingClient:
    """Groq-primary embedding client with sentence-transformers fallback.

    Always returns a plain Python list[float] from encode(), so callers
    don't need to call .tolist() themselves.
    """

    def __init__(
        self,
        groq_api_key: str | None,
        model: str = DEFAULT_EMBEDDING_MODEL,
    ) -> None:
        self._groq_client: openai.OpenAI | None = None
        self._st_model = None
        self.model = model

        if groq_api_key:
            self._groq_client = openai.OpenAI(
                api_key=groq_api_key,
                base_url="https://api.groq.com/openai/v1",
            )

    def encode(self, text: str) -> list[float]:
        if self._groq_client is not None:
            try:
                resp = self._groq_client.embeddings.create(
                    input=text,
                    model=self.model,
                )
                return resp.data[0].embedding
            except openai.APIError:
                warnings.warn(
                    "Groq embedding request failed — falling back to sentence-transformers",
                    stacklevel=2,
                )

        # Lazy-load sentence-transformers so the import cost is deferred
        if self._st_model is None:
            from sentence_transformers import SentenceTransformer
            self._st_model = SentenceTransformer("all-MiniLM-L6-v2")
        return self._st_model.encode(text).tolist()


def build_embedding_client(config: dict | None = None) -> EmbeddingClient:
    """Build an EmbeddingClient from .env config.

    Uses GROQ_API_KEY for the primary Groq embeddings endpoint.
    Falls back silently to sentence-transformers when the key is absent.
    """
    if config is None:
        config = dotenv_values()
    groq_key: str | None = config.get("GROQ_API_KEY") or None
    model = config.get("EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL
    if not groq_key:
        warnings.warn(
            "GROQ_API_KEY not set — embeddings will use sentence-transformers only",
            stacklevel=2,
        )
    return EmbeddingClient(groq_key, model)
