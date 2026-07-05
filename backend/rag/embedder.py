"""
embedder.py — converts text to vector embeddings using Google gemini-embedding-001.

Calls the Google Generative Language API directly.
Runs entirely via API — no local GPU needed.
Produces 3072-dimensional vectors.
"""

import requests

from backend.config import settings
from backend.observability.logging import get_logger

log = get_logger(__name__)

# Google embedding model — available on free Gemini API key
EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIM = 3072

# Google API endpoint
EMBED_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/"
    f"{EMBEDDING_MODEL}:embedContent"
)

# Maximum texts to embed in one batch (API limit)
BATCH_SIZE = 20


class EmbedderError(Exception):
    """Raised when embedding fails."""
    pass


def embed_text(text: str) -> list[float]:
    """
    Convert a single text string to a vector embedding.

    Args:
        text: the text to embed

    Returns:
        List of floats (3072 dimensions)

    Raises:
        EmbedderError: if the API call fails
    """
    results = embed_batch([text])
    return results[0]


def embed_batch(texts: list[str]) -> list[list[float]]:
    """
    Convert a list of texts to vector embeddings.
    Processes in batches to respect API limits.

    Args:
        texts: list of strings to embed

    Returns:
        List of embedding vectors, one per input text

    Raises:
        EmbedderError: if the API call fails
    """
    if not texts:
        return []

    all_embeddings = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i: i + BATCH_SIZE]

        log.info(
            "embedder.embedding_batch",
            batch_num=i // BATCH_SIZE + 1,
            batch_size=len(batch),
        )

        for text in batch:
            embedding = _embed_single(text)
            all_embeddings.append(embedding)

    log.info("embedder.done", total=len(all_embeddings))
    return all_embeddings


def _embed_single(text: str) -> list[float]:
    """
    Call the Google embedding API for a single text.

    Args:
        text: the text to embed

    Returns:
        List of floats

    Raises:
        EmbedderError: if the API call fails
    """
    payload = {
        "model": EMBEDDING_MODEL,
        "content": {
            "parts": [{"text": text}]
        }
    }

    try:
        response = requests.post(
            EMBED_URL,
            json=payload,
            params={"key": settings.gemini_api_key},
            timeout=30,
        )
    except requests.RequestException as e:
        raise EmbedderError(f"Network error calling embedding API: {e}") from e

    if response.status_code != 200:
        raise EmbedderError(
            f"Embedding API returned {response.status_code}: {response.text[:200]}"
        )

    data = response.json()
    try:
        return data["embedding"]["values"]
    except KeyError as e:
        raise EmbedderError(f"Unexpected API response format: {data}") from e


def get_embedding_dimension() -> int:
    """
    Return the dimension of gemini-embedding-001 vectors.
    Used when creating the Qdrant collection.
    """
    return EMBEDDING_DIM