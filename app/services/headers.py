"""In-memory Excel workbook processing and schema header mapping."""

import io
import logging
from typing import Any, Dict, Optional, Union
import pandas as pd

from app.cards import CardConfig, get_card_config

logger = logging.getLogger(__name__)


def read_excel_bytes(data: bytes, header: Any = 0) -> pd.DataFrame:
    """Read an Excel file from bytes purely in memory using calamine if available, falling back to openpyxl.

    Logs a data-free warning if falling back to openpyxl.
    All cell contents are loaded with dtype=str to preserve leading zeros, exact IDs, and codes.
    Never writes to disk.
    """
    buffer = io.BytesIO(data)
    try:
        import python_calamine  # noqa: F401
        return pd.read_excel(buffer, header=header, dtype=str, engine="calamine")
    except Exception as err:
        logger.warning(
            "Calamine engine unavailable or failed to parse workbook (%s); falling back to openpyxl. Performance will be degraded.",
            type(err).__name__,
        )
        buffer.seek(0)
        df = pd.read_excel(buffer, header=header, dtype=str, engine="openpyxl")
        df.attrs["engine_fallback"] = True
        return df


def add_headers(
    data: bytes,
    card: Union[str, CardConfig, Dict[str, Any]],
) -> Dict[str, Any]:
    """Validate and apply schema headers to a raw header-less Excel workbook.

    Processing logic:
    1. Read workbook in-memory with header=None and dtype=str.
    2. Drop rows where all cells are empty or NaN, then reset index.
    3. Detect if the first row already equals the expected column names (already has headers).
    4. Validate column count against card schema expected_columns.
    5. Return structured result dict: ok flag, DataFrame (only if ok), row count, column counts, and human message.
    NOTE: In Column Addition, values are NEVER altered or padded. Exported values equal input values exactly.
    """
    card_cfg = get_card_config(card)
    expected_columns = list(card_cfg.expected_columns)
    expected_count = len(expected_columns)

    try:
        df = read_excel_bytes(data, header=None)
    except Exception as e:
        return {
            "ok": False,
            "df": None,
            "rows": 0,
            "found_columns": 0,
            "expected_columns": expected_count,
            "message": f"Failed to read Excel workbook: {str(e)}",
        }

    # Drop rows where all elements are NaN, empty string, or whitespace
    is_empty_cell = df.isna() | df.apply(lambda col: col.astype(str).str.strip().eq(""))
    all_empty_rows = is_empty_cell.all(axis=1)
    df = df[~all_empty_rows].reset_index(drop=True)

    found_columns = df.shape[1]
    rows = df.shape[0]

    if rows == 0:
        return {
            "ok": False,
            "df": None,
            "rows": 0,
            "found_columns": found_columns,
            "expected_columns": expected_count,
            "message": "The uploaded Excel file contains no data rows.",
        }

    # Detect if the file already has headers in the first row
    first_row_values = [
        str(val).strip() if pd.notna(val) else "" for val in df.iloc[0].tolist()
    ]
    if first_row_values == expected_columns:
        return {
            "ok": False,
            "df": None,
            "rows": rows,
            "found_columns": found_columns,
            "expected_columns": expected_count,
            "message": f"File already contains {card_cfg.label} column headers. Use the Analysis module instead.",
        }

    # Check column count match
    if found_columns != expected_count:
        return {
            "ok": False,
            "df": None,
            "rows": rows,
            "found_columns": found_columns,
            "expected_columns": expected_count,
            "message": (
                f"Column count mismatch: found {found_columns} columns, "
                f"expected {expected_count} for {card_cfg.label}."
            ),
        }

    # Assign column headers (PADDING MUST NOT ALTER COLUMN ADDITION EXPORT)
    df.columns = expected_columns

    fallback_used = df.attrs.get("engine_fallback", False)
    msg = f"Successfully mapped {expected_count} columns for {card_cfg.label}."
    if fallback_used:
        msg += " (Warning: File loaded using fallback engine openpyxl; loading was slow.)"

    return {
        "ok": True,
        "df": df,
        "rows": rows,
        "found_columns": found_columns,
        "expected_columns": expected_count,
        "message": msg,
        "used_fallback_engine": fallback_used,
    }


def to_xlsx_bytes(df: pd.DataFrame) -> bytes:
    """Serialize DataFrame to .xlsx bytes in memory. Never touches disk."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return buffer.getvalue()

