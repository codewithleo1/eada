"""
upload.py — POST /upload endpoint for data file uploads.

Accepts CSV, Excel, JSON, Parquet files.
Saves to uploads/ with a UUID filename.
Returns file_id + schema info for the frontend to use in chat.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse

from backend.api.deps import get_current_user
from backend.tools.file_tool import get_file_info, FileToolError, SUPPORTED_EXTENSIONS
from backend.observability.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])

# Where uploaded files are stored — relative to project root
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Max file size: 50MB
MAX_FILE_SIZE = 50 * 1024 * 1024


@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
) -> JSONResponse:
    """
    Upload a data file for analysis.

    - Validates file extension
    - Saves to uploads/ with a UUID-based filename
    - Extracts schema and sample rows via file_tool
    - Returns file_id to use in subsequent chat messages

    Auth required: Bearer token
    """
    # 1. Validate extension
    original_name = file.filename or "unknown"
    ext = Path(original_name).suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type: '{ext}'. "
                f"Allowed: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            ),
        )

    # 2. Read file content + check size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is 50MB.",
        )

    # 3. Save with UUID filename to avoid collisions
    file_id = str(uuid.uuid4())
    save_path = UPLOAD_DIR / f"{file_id}{ext}"

    try:
        save_path.write_bytes(content)
    except Exception as e:
        log.error("upload.save_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to save file.")

    log.info(
        "upload.saved",
        file_id=file_id,
        original=original_name,
        size=len(content),
        path=str(save_path),
    )

    # 4. Extract schema + sample via file_tool
    try:
        file_info = get_file_info(str(save_path))
    except FileToolError as e:
        # Clean up the saved file if we can't read it
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(e))
    
    # 5. Return file_id + metadata
    return JSONResponse(content={
        "file_id": file_id,
        "original_filename": original_name,
        "extension": ext,
        "row_count": file_info["row_count"],
        "columns": file_info["columns"],
        "sample": file_info["sample"],
        "message": f"File '{original_name}' uploaded successfully. You can now ask questions about it.",
    })