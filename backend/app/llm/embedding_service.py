import hashlib
import math
import re
from typing import Protocol

from openai import OpenAI

from app.core.config import settings
from app.llm.embedding_text import EMBEDDING_DIMENSION

_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "about",
        "is",
        "are",
        "was",
        "were",
    }
)


class EmbeddingService(Protocol):
    def embed(self, text: str) -> list[float]: ...


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [token for token in tokens if token not in _STOP_WORDS]


class FakeEmbeddingService:
    """Deterministic bag-of-words style vectors for tests without OpenAI."""

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIMENSION
        for token in _tokenize(text):
            digest = hashlib.sha256(token.encode()).digest()
            for offset in range(8):
                index = int.from_bytes(digest[offset:offset + 2], "big") % EMBEDDING_DIMENSION
                vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]


class OpenAIEmbeddingService:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def embed(self, text: str) -> list[float]:
        response = self._client.embeddings.create(input=text, model=self._model)
        return list(response.data[0].embedding)


def create_embedding_service() -> EmbeddingService:
    if settings.openai_api_key:
        return OpenAIEmbeddingService(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
        )
    return FakeEmbeddingService()


def create_embedding_service_for_api_key(api_key: str | None) -> EmbeddingService:
    if api_key:
        return OpenAIEmbeddingService(
            api_key=api_key,
            model=settings.openai_embedding_model,
        )
    return FakeEmbeddingService()
