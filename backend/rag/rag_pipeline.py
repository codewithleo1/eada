"""
rag_pipeline.py — orchestrates the full RAG (Retrieval Augmented Generation) flow.

Ingest:  file → chunker → embedder → Qdrant
Retrieve: question → embedder → Qdrant search → context chunks
"""

from backend.rag.chunker import chunk_document, ChunkerError
from backend.rag.embedder import embed_text, embed_batch, get_embedding_dimension, EmbedderError
from backend.rag.vector_store import ensure_collection, upsert_chunks, search, VectorStoreError
from backend.observability.logging import get_logger

log = get_logger(__name__)


class RAGPipelineError(Exception):
    """Raised when the RAG pipeline fails."""
    pass


def ingest_document(file_path: str, doc_id: str) -> dict:
    """
    Full ingestion pipeline: read file → chunk → embed → store in Qdrant.

    Args:
        file_path: path to the document file
        doc_id:    unique UUID for this document

    Returns:
        {
            "doc_id": str,
            "source": str,
            "num_chunks": int,
            "embedding_dim": int,
        }

    Raises:
        RAGPipelineError: if any step fails
    """
    log.info("rag_pipeline.ingest_start", doc_id=doc_id, path=file_path)

    # Step 1 — chunk the document
    try:
        chunks = chunk_document(file_path)
    except ChunkerError as e:
        raise RAGPipelineError(f"Chunking failed: {e}") from e

    log.info("rag_pipeline.chunked", doc_id=doc_id, num_chunks=len(chunks))

    # Step 2 — embed all chunks in one batch
    texts = [chunk["text"] for chunk in chunks]
    try:
        embeddings = embed_batch(texts)
    except EmbedderError as e:
        raise RAGPipelineError(f"Embedding failed: {e}") from e

    log.info("rag_pipeline.embedded", doc_id=doc_id, num_embeddings=len(embeddings))

    # Step 3 — ensure Qdrant collection exists
    embedding_dim = get_embedding_dimension()
    try:
        ensure_collection(embedding_dim)
    except VectorStoreError as e:
        raise RAGPipelineError(f"Qdrant collection setup failed: {e}") from e

    # Step 4 — store in Qdrant
    try:
        num_stored = upsert_chunks(chunks, embeddings, doc_id)
    except VectorStoreError as e:
        raise RAGPipelineError(f"Qdrant upsert failed: {e}") from e

    log.info(
        "rag_pipeline.ingest_complete",
        doc_id=doc_id,
        num_chunks=num_stored,
    )

    return {
        "doc_id": doc_id,
        "source": chunks[0]["source"] if chunks else "",
        "num_chunks": num_stored,
        "embedding_dim": embedding_dim,
    }


def retrieve_context(
    question: str,
    top_k: int = 5,
    doc_id: str | None = None,
) -> list[dict]:
    """
    Retrieve the most relevant document chunks for a question.

    Args:
        question: the user's question
        top_k:    number of chunks to retrieve
        doc_id:   if provided, restrict search to this document only

    Returns:
        List of chunk dicts with text + metadata + similarity score

    Raises:
        RAGPipelineError: if embedding or search fails
    """
    log.info("rag_pipeline.retrieve_start", question=question[:80])

    # Embed the question
    try:
        query_vector = embed_text(question)
    except EmbedderError as e:
        raise RAGPipelineError(f"Query embedding failed: {e}") from e

    # Search Qdrant
    try:
        results = search(query_vector, top_k=top_k, doc_id=doc_id)
    except VectorStoreError as e:
        raise RAGPipelineError(f"Qdrant search failed: {e}") from e

    log.info(
        "rag_pipeline.retrieve_done",
        num_results=len(results),
        top_score=results[0]["score"] if results else 0,
    )

    return results


def build_rag_context(chunks: list[dict]) -> str:
    """
    Format retrieved chunks into a context string for the LLM.

    Args:
        chunks: list of chunk dicts from retrieve_context()

    Returns:
        Formatted string with source labels and chunk text
    """
    if not chunks:
        return "No relevant document sections found."

    parts = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(
            f"[Source: {chunk['source']}, Section {chunk['chunk_index'] + 1}, "
            f"Relevance: {chunk['score']:.2f}]\n{chunk['text']}"
        )

    return "\n\n---\n\n".join(parts)