"""Turns text into vectors through an OpenAI-compatible embeddings endpoint. No Flask here.

Configured by EMBEDDINGS_URL (base URL, for example http://llama-embed:8080/v1), EMBEDDINGS_MODEL
and EMBEDDINGS_API_KEY. Without EMBEDDINGS_URL there is no embedder: writers send their own vectors
and search runs on text alone. EMBEDDINGS_QUERY_PREFIX is put before search queries, for models
that embed queries and documents differently (Qwen3-Embedding takes an instruction).
"""

import os
from dataclasses import dataclass

import requests

from core.log import get_logger

logger = get_logger("knowledge.embedder")

TIMEOUT_SECONDS = 30
BATCH = 64


class EmbeddingError(RuntimeError):
    pass


@dataclass(frozen=True)
class Embedder:
    url: str
    model: str
    api_key: str | None = None
    query_prefix: str = ""

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH):
            vectors.extend(self._post(texts[start : start + BATCH]))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed([self.query_prefix + text])[0]

    def _post(self, batch: list[str]) -> list[list[float]]:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            response = requests.post(
                self.url.rstrip("/") + "/embeddings",
                json={"model": self.model, "input": batch},
                headers=headers,
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = sorted(response.json()["data"], key=lambda row: row["index"])
            vectors = [[float(x) for x in row["embedding"]] for row in data]
        except (requests.RequestException, ValueError, KeyError, TypeError) as e:
            logger.warning("embedding request failed: %s", e)
            raise EmbeddingError("The embedding service failed") from e
        if len(vectors) != len(batch):
            raise EmbeddingError("The embedding service returned the wrong number of vectors")
        return vectors


def configured() -> Embedder | None:
    url = os.environ.get("EMBEDDINGS_URL", "").strip()
    if not url:
        return None
    return Embedder(
        url=url,
        model=os.environ.get("EMBEDDINGS_MODEL", "").strip() or "default",
        api_key=os.environ.get("EMBEDDINGS_API_KEY") or None,
        query_prefix=os.environ.get("EMBEDDINGS_QUERY_PREFIX", ""),
    )
