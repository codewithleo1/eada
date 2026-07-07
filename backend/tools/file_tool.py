"""
file_tool.py - reads uploaded data files and extracts schema + sample rows.

Supports: CSV, Excel (.xlsx/.xls), JSON, Parquet
Returns structured metadata the LLM uses to write accurate SQL queries.
"""

import json
import math
from pathlib import Path

import pandas as pd

from backend.observability.logging import get_logger

log = get_logger(__name__)

# File extensions we accept
SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json", ".parquet"}


class FileToolError(Exception):
    """Raised when file_tool cannot process a file."""
    pass


def get_file_info(file_path: str) -> dict:
    """
    Read a data file and return its schema and a sample of rows.

    Args:
        file_path: absolute or relative path to the uploaded file

    Returns:
        {
            "file_path": str,
            "extension": str,
            "row_count": int,
            "columns": [{"name": str, "dtype": str}, ...],
            "sample": [{"col": value, ...}, ...],   # first 5 rows
            "sql_table_ref": str,   # how DuckDB should reference this file
        }

    Raises:
        FileToolError: if extension unsupported or file unreadable
    """
    path = Path(file_path)

    if not path.exists():
        raise FileToolError(f"File not found: {file_path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise FileToolError(
            f"Unsupported file type: {ext}. "
            f"Supported: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    log.info("file_tool.reading", path=str(path), ext=ext)

    try:
        df = _read_file(path, ext)
    except Exception as e:
        raise FileToolError(f"Failed to read file: {e}") from e

    # Build column metadata
    columns = [
        {"name": col, "dtype": str(df[col].dtype)}
        for col in df.columns
    ]

    # First 5 rows as plain dicts (JSON-serialisable)
    sample = _safe_sample(df, n=5)

    # How DuckDB references this file in a query
    sql_table_ref = _build_sql_ref(path, ext)

    info = {
        "file_path": str(path),
        "extension": ext,
        "row_count": len(df),
        "columns": columns,
        "sample": sample,
        "sql_table_ref": sql_table_ref,
    }

    log.info(
        "file_tool.done",
        rows=info["row_count"],
        cols=len(columns),
        ext=ext,
    )
    return info


def _read_file(path: Path, ext: str) -> pd.DataFrame:
    """Read file into a pandas DataFrame based on extension."""
    if ext == ".csv":
        return pd.read_csv(path)
    elif ext in (".xlsx", ".xls"):
        return pd.read_excel(path)
    elif ext == ".json":
        return pd.read_json(path)
    elif ext == ".parquet":
        return pd.read_parquet(path)
    else:
        raise FileToolError(f"Unhandled extension: {ext}")


def _safe_sample(df: pd.DataFrame, n: int = 5) -> list[dict]:
    """
    Return first n rows as a list of dicts.
    Converts NaN, inf, and other non-JSON-serialisable types to safe values.
    """
    sample_df = df.head(n)
    rows = []
    for _, row in sample_df.iterrows():
        clean_row = {}
        for col, val in row.items():
            # Replace NaN and inf with None
            try:
                if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                    clean_row[col] = None
                    continue
            except (TypeError, ValueError):
                pass
            # Convert anything else that is not JSON-serialisable to string
            try:
                json.dumps(val)
                clean_row[col] = val
            except (TypeError, ValueError):
                clean_row[col] = str(val)
        rows.append(clean_row)
    return rows


def _build_sql_ref(path: Path, ext: str) -> str:
    """
    Return the DuckDB SQL snippet to reference this file in a FROM clause.
    """
    p = path.as_posix()

    if ext == ".csv":
        return f"read_csv('{p}', auto_detect=True)"
    elif ext in (".xlsx", ".xls"):
        return f"excel:'{p}'"
    elif ext == ".parquet":
        return f"read_parquet('{p}')"
    elif ext == ".json":
        return f"read_json_auto('{p}')"
    else:
        return f"'{p}'"