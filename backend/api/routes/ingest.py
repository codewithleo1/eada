"""
ingest.py — POST /ingest endpoint for document ingestion into Qdrant.

Accepts PDF, DOCX, TXT, MD files.
Chunks, embeds, and stores them in Qdrant for RAG retrieval.
Returns doc_id to use in subsequent chat messages.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse

from backend.api.deps import get_current_user
from backend.rag.chunker import SUPPORTED_DOC_EXTENSIONS
from backend.rag.rag_pipeline import ingest_document, RAGPipelineError
from backend.observability.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB for documents


@router.post("")
async def ingest_document_endpoint(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
) -> JSONResponse:
    """
    Upload and index a document for RAG-based Q&A.

    - Validates file extension
    - Saves to uploads/ with UUID filename
    - Chunks, embeds, and stores in Qdrant
    - Returns doc_id to use in chat messages

    Auth required: Bearer token
    """
    # 1. Validate extension
    original_name = file.filename or "unknown"
    ext = Path(original_name).suffix.lower()

    if ext not in SUPPORTED_DOC_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported document type: '{ext}'. "
                f"Allowed: {', '.join(sorted(SUPPORTED_DOC_EXTENSIONS))}"
            ),
        )

    # 2. Read + size check
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum size is 20MB.",
        )

    # 3. Save with UUID filename
    doc_id = str(uuid.uuid4())
    save_path = UPLOAD_DIR / f"{doc_id}{ext}"

    try:
        save_path.write_bytes(content)
    except Exception as e:
        log.error("ingest.save_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to save file.")

    log.info(
        "ingest.saved",
        doc_id=doc_id,
        original=original_name,
        size=len(content),
    )

    # 4. Run RAG ingestion pipeline
    try:
        result = ingest_document(str(save_path), doc_id)
    except RAGPipelineError as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(e))

    # 5. Return doc_id + metadata
    return JSONResponse(content={
        "doc_id": doc_id,
        "original_filename": original_name,
        "extension": ext,
        "num_chunks": result["num_chunks"],
        "embedding_dim": result["embedding_dim"],
        "message": (
            f"Document '{original_name}' ingested successfully. "
            f"Split into {result['num_chunks']} chunks and indexed in Qdrant. "
            f"You can now ask questions about it."
        ),
    })