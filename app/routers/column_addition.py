"""Column Addition Router: upload, server-side pagination preview, in-memory export, and data wipe."""

import io
import logging
import math
import time
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from app.cards import CARDS
from app.config import settings
from app.services.concurrency import run_parse_task
from app.services.headers import add_headers, to_xlsx_bytes
from app.store import session_store
from app.uploads import read_limited_body

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/column-addition", tags=["column-addition"])


def _validate_session(x_session_id: Optional[str]):
    """Verify session is provided, active, and unexpired. Returns SessionData."""
    if not x_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Session-Id header.",
        )
    session = session_store.get_session(x_session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or not found. Please re-upload your file.",
        )
    return session


@router.post("/{card_key}/upload")
async def upload_file(
    card_key: str,
    request: Request,
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    x_filename: Optional[str] = Header(None, alias="X-Filename"),
):
    """Upload raw header-less Excel workbook for schema validation and header addition.
    
    Operates strictly in-memory (no disk writes).
    Validates column count and detects pre-existing headers.
    """
    session = _validate_session(x_session_id)

    key = card_key.lower().strip()
    if key not in CARDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported card type '{card_key}'. Valid cards: {list(CARDS.keys())}",
        )

    if not x_filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-Filename header.",
        )
    if not x_filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .xlsx files are supported.",
        )

    # Read body chunks up to 50 MB
    file_bytes = await read_limited_body(request, max_bytes=settings.MAX_UPLOAD_SIZE_BYTES)

    # Process through concurrency semaphore in threadpool
    t0 = time.perf_counter()
    result = await run_parse_task(add_headers, file_bytes, key)
    duration = time.perf_counter() - t0

    # Privacy rule: Log metadata only, never cell values
    logger.info("Parsed %s (%d bytes) in %.2fs", key, len(file_bytes), duration)

    if not result["ok"]:
        session.coladd.clear()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result["message"],
        )

    df = result["df"]
    total_rows = len(df)
    is_large_file = len(file_bytes) > (30 * 1024 * 1024)

    # Store DataFrame in session
    session.coladd = {
        "df": df,
        "card_key": key,
        "filename": x_filename,
        "is_large_file": is_large_file,
    }

    # Generate initial preview (page 1, page_size 25)
    page_size = 25
    total_pages = max(1, math.ceil(total_rows / page_size))
    cols = [c for c in df.columns if not c.startswith("_raw_")]
    preview_df = df.iloc[0:page_size]

    preview_rows = []
    for row in preview_df[cols].itertuples(index=False, name=None):
        preview_rows.append({
            cols[i]: ("" if val is None or pd.isna(val) else str(val))
            for i, val in enumerate(row)
        })

    return {
        "ok": True,
        "rows": total_rows,
        "columns": cols,
        "column_count": len(cols),
        "card_key": key,
        "is_large_file": is_large_file,
        "preview": {
            "page": 1,
            "page_size": page_size,
            "total_rows": total_rows,
            "total_pages": total_pages,
            "columns": cols,
            "rows": preview_rows,
        },
    }


@router.get("/preview")
async def get_preview(
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(25, description="Rows per page (25, 50, or 100)"),
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
):
    """Retrieve server-side paginated preview rows for the current column-addition dataset."""
    session = _validate_session(x_session_id)

    if page_size not in (25, 50, 100):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="page_size must be 25, 50, or 100",
        )

    if not session.coladd or "df" not in session.coladd:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No column addition data found. Please upload an Excel file first.",
        )

    df: pd.DataFrame = session.coladd["df"]
    total_rows = len(df)
    total_pages = max(1, math.ceil(total_rows / page_size))
    cols = [c for c in df.columns if not c.startswith("_raw_")]

    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_rows)

    if start_idx < total_rows:
        sub_df = df.iloc[start_idx:end_idx]
        rows_data = []
        for row in sub_df[cols].itertuples(index=False, name=None):
            rows_data.append({
                cols[i]: ("" if val is None or pd.isna(val) else str(val))
                for i, val in enumerate(row)
            })
    else:
        rows_data = []

    return {
        "page": page,
        "page_size": page_size,
        "total_rows": total_rows,
        "total_pages": total_pages,
        "columns": cols,
        "rows": rows_data,
    }


@router.get("/export")
async def export_excel(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
):
    """Export the mapped DataFrame as a .xlsx file in memory via xlsxwriter."""
    session = _validate_session(x_session_id)

    if not session.coladd or "df" not in session.coladd:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No column addition data to export. Please upload an Excel file first.",
        )

    df: pd.DataFrame = session.coladd["df"]
    card_key = session.coladd.get("card_key", "card")
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    export_filename = f"{card_key}_with_headers_{date_str}.xlsx"

    # Export purely in memory via thread pool
    xlsx_bytes = await run_in_threadpool(to_xlsx_bytes, df)

    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{export_filename}"',
            "Content-Length": str(len(xlsx_bytes)),
        },
    )


@router.delete("")
async def delete_dataset(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
):
    """Explicitly wipe the column-addition dataset from the in-memory session."""
    session = _validate_session(x_session_id)
    session.coladd.clear()
    return {"status": "deleted"}
