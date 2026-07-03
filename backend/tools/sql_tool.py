"""
sql_tool.py — executes DuckDB SQL queries against uploaded data files.

DuckDB runs entirely in-process — no server needed.
Supports CSV, Parquet, JSON natively.
Excel is handled via pandas → DuckDB in-memory table.
"""

from pathlib import Path

import duckdb
import pandas as pd

from backend.observability.logging import get_logger

log = get_logger(__name__)

# Maximum rows we'll return to avoid overwhelming the LLM context
MAX_RESULT_ROWS = 500


class SqlToolError(Exception):
    """Raised when sql_tool cannot execute a query."""
    pass


def execute_query(sql: str, file_path: str) -> dict:
    """
    Execute a DuckDB SQL query against an uploaded file.

    Args:
        sql:       A valid DuckDB SQL query string
        file_path: Path to the uploaded file (CSV, Excel, JSON, Parquet)

    Returns:
        {
            "sql": str,               # the query that was run
            "columns": [str, ...],    # column names in result
            "rows": [dict, ...],      # result rows (max 500)
            "row_count": int,         # total rows returned
            "truncated": bool,        # True if result was capped at MAX_RESULT_ROWS
        }

    Raises:
        SqlToolError: if the query fails or file is unreadable
    """
    path = Path(file_path)
    if not path.exists():
        raise SqlToolError(f"File not found: {file_path}")

    ext = path.suffix.lower()
    log.info("sql_tool.executing", sql=sql[:120], ext=ext)

    try:
        con = duckdb.connect()  # in-memory, throwaway connection

        if ext in (".xlsx", ".xls"):
            result_df = _execute_on_excel(con, sql, path)
        else:
            result_df = _execute_on_file(con, sql, path)

        con.close()

    except SqlToolError:
        raise
    except Exception as e:
        raise SqlToolError(f"Query failed: {e}") from e

    # Cap result size
    truncated = len(result_df) > MAX_RESULT_ROWS
    if truncated:
        result_df = result_df.head(MAX_RESULT_ROWS)

    columns = list(result_df.columns)
    rows = _df_to_rows(result_df)

    log.info(
        "sql_tool.done",
        row_count=len(rows),
        truncated=truncated,
    )

    return {
        "sql": sql,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
    }


def _execute_on_file(
    con: duckdb.DuckDBPyConnection,
    sql: str,
    path: Path,
) -> pd.DataFrame:
    """
    Execute SQL for CSV, Parquet, JSON files.
    Uses pandas to load the file first, then registers as a DuckDB view.
    This avoids all CSV dialect / encoding sniffing issues.
    """
    ext = path.suffix.lower()

    if ext == ".csv":
        df = pd.read_csv(path)
    elif ext == ".parquet":
        df = pd.read_parquet(path)
    elif ext == ".json":
        df = pd.read_json(path)
    else:
        raise SqlToolError(f"Unsupported extension for file execution: {ext}")

    # Register the DataFrame as a view called 'data'
    con.register("data", df)

    # Rewrite the SQL to use 'data' instead of read_csv(...) etc.
    clean_sql = _replace_file_ref(sql, path)

    return con.execute(clean_sql).df()


def _execute_on_excel(
    con: duckdb.DuckDBPyConnection,
    sql: str,
    path: Path,
) -> pd.DataFrame:
    """
    Excel files can't be read natively by DuckDB.
    Load via pandas, register as a DuckDB view called 'data', then query.
    """
    df = pd.read_excel(path)
    con.register("data", df)

    clean_sql = _replace_file_ref(sql, path)
    return con.execute(clean_sql).df()


def _replace_file_ref(sql: str, path: Path) -> str:
    """
    Replace any file reference in the SQL with the DuckDB view name 'data'.

    Handles these patterns the LLM might generate:
      - read_csv('uploads/uuid.csv', auto_detect=True)
      - read_csv('uploads/uuid.csv', header=True, delim=',')
      - read_parquet('uploads/uuid.parquet')
      - read_json_auto('uploads/uuid.json')
      - excel:'uploads/uuid.xlsx'
      - 'uploads/uuid.csv'
      - uuid  (bare stem)
    """
    p = path.as_posix()
    name = path.name
    stem = path.stem

    replacements = [
        # Full read_csv(...) with any args — use regex-free approach
        f"read_csv('{p}', auto_detect=True)",
        f"read_csv('{p}', header=True, delim=',', quote='\"')",
        f"read_csv('{p}')",
        f"read_parquet('{p}')",
        f"read_json_auto('{p}')",
        f"read_json('{p}')",
        f"excel:'{p}'",
        f"'{p}'",
        f"'{name}'",
        stem,
    ]

    for ref in replacements:
        if ref in sql:
            sql = sql.replace(ref, "data")
            break  # only replace the first match

    return sql


def _df_to_rows(df: pd.DataFrame) -> list[dict]:
    """
    Convert DataFrame to list of plain dicts.
    Handles non-JSON-serialisable types (numpy int64, NaT, Timestamp, etc.)
    """
    import json
    rows = []
    for _, row in df.iterrows():
        clean = {}
        for col, val in row.items():
            try:
                json.dumps(val)
                clean[col] = val
            except (TypeError, ValueError):
                clean[col] = str(val)
        rows.append(clean)
    return rows