"""In-memory Excel workbook processing, schema header mapping, and streaming export."""

import csv
import io
import logging
from typing import Any, Dict, Generator, Optional, Union
import numpy as np
import pandas as pd
import xlsxwriter

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


def to_xlsx_buffer(df: pd.DataFrame) -> io.BytesIO:
    """Serialize DataFrame to an in-memory BytesIO buffer using xlsxwriter with optimized tight write loops.

    Ensures:
    - Normal in-memory mode with BytesIO (never constant_memory which writes temp files).
    - strings_to_formulas=False (prevents =1+1, +cmd, @x being interpreted as formulas).
    - strings_to_urls=False (prevents http://example.com being turned into hyperlinks).
    - strings_to_numbers=False (prevents '00000003' losing leading zeros).
    - Zero redundant copying of the output buffer.
    - Exact 100% preservation of text and raw input values.
    """
    buffer = io.BytesIO()
    workbook = xlsxwriter.Workbook(
        buffer,
        {
            "in_memory": True,
            "strings_to_formulas": False,
            "strings_to_urls": False,
            "strings_to_numbers": False,
        },
    )
    worksheet = workbook.add_worksheet("Sheet1")

    # Write headers
    headers = list(df.columns)
    for col_idx, h in enumerate(headers):
        worksheet.write_string(0, col_idx, str(h))

    # Vectorized conversion to numpy object array and null mask handling
    values = df.to_numpy(dtype=object)
    null_mask = pd.isna(values)
    values[null_mask] = ""

    n_rows, n_cols = values.shape
    write_str = worksheet.write_string
    write_blk = worksheet.write_blank

    for r in range(n_rows):
        row_idx = r + 1
        for c in range(n_cols):
            val = values[r, c]
            if val == "":
                write_blk(row_idx, c, None)
            else:
                write_str(row_idx, c, str(val) if not isinstance(val, str) else val)

    workbook.close()
    buffer.seek(0)
    return buffer


def to_xlsx_bytes(df: pd.DataFrame) -> bytes:
    """Backward-compatible helper returning bytes from to_xlsx_buffer."""
    buf = to_xlsx_buffer(df)
    return buf.getvalue()


def iter_csv_chunks(df: pd.DataFrame, chunk_size: int = 20_000) -> Generator[bytes, None, None]:
    """Stream DataFrame in chunks encoded as UTF-8 with BOM for Excel compatibility.

    - Writes in chunks of ~20,000 rows.
    - Encoded UTF-8 with BOM (b'\xef\xbb\xbf') at the start.
    - Header row emitted only on the first chunk.
    - Uses pandas to_csv with QUOTE_MINIMAL and CRLF line terminator.
    - Writes through io.TextIOWrapper over an in-memory BytesIO per chunk.
    - Zero disk persistence, no full-file buffer.
    - Preserves values exactly as stored (no padding, no conversion).
    """
    total_rows = len(df)
    first = True

    if total_rows == 0:
        buf = io.BytesIO()
        buf.write(b"\xef\xbb\xbf")
        text_io = io.TextIOWrapper(buf, encoding="utf-8", newline="", write_through=True)
        pd.DataFrame(columns=df.columns).to_csv(
            text_io,
            header=True,
            index=False,
            quoting=csv.QUOTE_MINIMAL,
            lineterminator="\r\n",
        )
        text_io.detach()
        yield buf.getvalue()
        return

    for start in range(0, total_rows, chunk_size):
        chunk = df.iloc[start : start + chunk_size]
        buf = io.BytesIO()
        if first:
            buf.write(b"\xef\xbb\xbf")
            header = True
            first = False
        else:
            header = False

        text_io = io.TextIOWrapper(buf, encoding="utf-8", newline="", write_through=True)
        chunk.to_csv(
            text_io,
            header=header,
            index=False,
            quoting=csv.QUOTE_MINIMAL,
            lineterminator="\r\n",
            na_rep="",
        )
        text_io.detach()
        yield buf.getvalue()
