"""
chunker.py — splits documents into overlapping text chunks for RAG.

Supports: PDF (.pdf), Word (.docx), plain text (.txt, .md)
Returns a list of chunk dicts ready to be embedded and stored in Qdrant.
"""

from pathlib import Path

from backend.observability.logging import get_logger

log = get_logger(__name__)

# Supported document extensions
SUPPORTED_DOC_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}

# Chunk size in characters (roughly 400-500 words)
CHUNK_SIZE = 1500

# Overlap between consecutive chunks in characters
CHUNK_OVERLAP = 200


class ChunkerError(Exception):
    """Raised when chunker cannot process a document."""
    pass


def chunk_document(file_path: str) -> list[dict]:
    """
    Read a document and split it into overlapping text chunks.

    Args:
        file_path: path to the document file

    Returns:
        List of chunk dicts:
        [
            {
                "text": str,         # the chunk text
                "chunk_index": int,  # position in document
                "source": str,       # original filename
                "char_start": int,   # character offset in full text
            },
            ...
        ]

    Raises:
        ChunkerError: if file not found, unsupported type, or read error
    """
    path = Path(file_path)

    if not path.exists():
        raise ChunkerError(f"File not found: {file_path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_DOC_EXTENSIONS:
        raise ChunkerError(
            f"Unsupported document type: {ext}. "
            f"Supported: {', '.join(sorted(SUPPORTED_DOC_EXTENSIONS))}"
        )

    log.info("chunker.reading", path=str(path), ext=ext)

    try:
        full_text = _extract_text(path, ext)
    except Exception as e:
        raise ChunkerError(f"Failed to read document: {e}") from e

    if not full_text.strip():
        raise ChunkerError("Document appears to be empty.")

    chunks = _split_into_chunks(full_text, source=path.name)

    log.info(
        "chunker.done",
        source=path.name,
        total_chars=len(full_text),
        num_chunks=len(chunks),
    )

    return chunks


def _extract_text(path: Path, ext: str) -> str:
    """Extract plain text from a document based on its extension."""
    if ext == ".pdf":
        return _extract_pdf(path)
    elif ext == ".docx":
        return _extract_docx(path)
    elif ext in (".txt", ".md"):
        return path.read_text(encoding="utf-8", errors="ignore")
    else:
        raise ChunkerError(f"Unhandled extension: {ext}")


def _extract_pdf(path: Path) -> str:
    """Extract text from a PDF using PyMuPDF."""
    import fitz  # pymupdf

    doc = fitz.open(str(path))
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n\n".join(pages)


def _extract_docx(path: Path) -> str:
    """Extract text from a Word document using python-docx."""
    from docx import Document

    doc = Document(str(path))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def _split_into_chunks(text: str, source: str) -> list[dict]:
    """
    Split text into overlapping chunks of CHUNK_SIZE characters.

    Uses a sliding window approach:
    - Move forward by (CHUNK_SIZE - CHUNK_OVERLAP) each step
    - Each chunk overlaps the previous by CHUNK_OVERLAP characters
    """
    chunks = []
    start = 0
    chunk_index = 0
    step = CHUNK_SIZE - CHUNK_OVERLAP

    while start < len(text):
        end = start + CHUNK_SIZE
        chunk_text = text[start:end].strip()

        if chunk_text:  # skip empty chunks
            chunks.append({
                "text": chunk_text,
                "chunk_index": chunk_index,
                "source": source,
                "char_start": start,
            })
            chunk_index += 1

        start += step

    return chunks