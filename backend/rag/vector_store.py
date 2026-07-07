"""
vector_store.py Ã¢â‚¬â€ stores and searches document chunks in Qdrant.

Each document chunk is stored as a vector + payload.
Search returns the top K most similar chunks to a query vector.
"""

from qdrant_client import QdrantClient
from backend.config import settings
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)

from backend.observability.logging import get_logger

log = get_logger(__name__)

# Qdrant connection Ã¢â‚¬â€ matches docker-compose.yml

# Collection name for RAG documents
COLLECTION_NAME = "eada_documents"

# Number of similar chunks to return per search
DEFAULT_TOP_K = 5


class VectorStoreError(Exception):
    """Raised when Qdrant operations fail."""
    pass


def get_client() -> QdrantClient:
    """Return a Qdrant client connected to our Docker instance."""
    return QdrantClient(url=settings.qdrant_url)


def ensure_collection(embedding_dim: int = 768) -> None:
    """
    Create the Qdrant collection if it doesn't already exist.

    Args:
        embedding_dim: size of the embedding vectors (768 for text-embedding-004)
    """
    client = get_client()

    existing = [c.name for c in client.get_collections().collections]

    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=embedding_dim,
                distance=Distance.COSINE,
            ),
        )
        log.info("vector_store.collection_created", name=COLLECTION_NAME)
    else:
        log.info("vector_store.collection_exists", name=COLLECTION_NAME)


def upsert_chunks(
    chunks: list[dict],
    embeddings: list[list[float]],
    doc_id: str,
) -> int:
    """
    Store document chunks and their embeddings in Qdrant.

    Args:
        chunks:     list of chunk dicts from chunker.py
        embeddings: list of embedding vectors, one per chunk
        doc_id:     unique ID for this document (UUID)

    Returns:
        Number of chunks stored

    Raises:
        VectorStoreError: if upsert fails
    """
    if len(chunks) != len(embeddings):
        raise VectorStoreError(
            f"Chunks ({len(chunks)}) and embeddings ({len(embeddings)}) count mismatch."
        )

    client = get_client()

    points = []
    for i, (chunk, vector) in enumerate(zip(chunks, embeddings)):
        # Use a deterministic integer ID based on doc_id + chunk_index
        point_id = _make_point_id(doc_id, chunk["chunk_index"])

        points.append(
            PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "text": chunk["text"],
                    "source": chunk["source"],
                    "chunk_index": chunk["chunk_index"],
                    "char_start": chunk["char_start"],
                    "doc_id": doc_id,
                },
            )
        )

    try:
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
        )
        log.info("vector_store.upserted", doc_id=doc_id, count=len(points))
    except Exception as e:
        raise VectorStoreError(f"Qdrant upsert failed: {e}") from e

    return len(points)


def search(
    query_vector: list[float],
    top_k: int = DEFAULT_TOP_K,
    doc_id: str | None = None,
) -> list[dict]:
    """
    Find the most similar chunks to a query vector.

    Args:
        query_vector: embedding of the user's question
        top_k:        number of results to return
        doc_id:       if provided, restrict search to this document only

    Returns:
        List of result dicts with text, source, chunk_index, doc_id, score
    """

    client = get_client()

    # Optional filter to restrict to a specific document
    query_filter = None
    if doc_id:
        query_filter = Filter(
            must=[
                FieldCondition(
                    key="doc_id",
                    match=MatchValue(value=doc_id),
                )
            ]
        )

    try:
        results = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        ).points
    except Exception as e:
        raise VectorStoreError(f"Qdrant search failed: {e}") from e

    return [
        {
            "text": r.payload["text"],
            "source": r.payload["source"],
            "chunk_index": r.payload["chunk_index"],
            "doc_id": r.payload["doc_id"],
            "score": r.score,
        }
        for r in results
    ]


def delete_document(doc_id: str) -> None:
    """
    Delete all chunks belonging to a document from Qdrant.

    Args:
        doc_id: the document UUID to delete
    """
    client = get_client()

    try:
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="doc_id",
                        match=MatchValue(value=doc_id),
                    )
                ]
            ),
        )
        log.info("vector_store.deleted", doc_id=doc_id)
    except Exception as e:
        raise VectorStoreError(f"Qdrant delete failed: {e}") from e


def _make_point_id(doc_id: str, chunk_index: int) -> int:
    """
    Generate a deterministic integer Qdrant point ID.
    Qdrant requires integer or UUID point IDs.
    We use a hash of doc_id + chunk_index.
    """
    import hashlib
    raw = f"{doc_id}:{chunk_index}"
    hash_hex = hashlib.md5(raw.encode()).hexdigest()
    # Take first 15 hex chars to stay within safe integer range
    return int(hash_hex[:15], 16)