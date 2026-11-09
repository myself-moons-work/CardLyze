"""Task 1 Router: TMS-ATM High-Risk Transaction Monitoring and Reporting.

Endpoints:
- POST /api/task1/{card_key}/upload: Upload workbook for Task 1 analysis.
- POST /api/task1/{card_key}/load-sample: Quick-load bundled local sample dataset.
- GET  /api/task1/dates: Get list of distinct dates in active dataset.
- POST /api/task1/{card_key}/detect: Execute Task 1 detection rule on chosen date.
- GET  /api/task1/export-csv: Download unmodified transactions for flagged individuals as CSV.
- GET  /api/task1/export-excel: Download unmodified transactions for flagged individuals as Excel.
- GET  /api/task1/export-alerts-csv: Download alert summary report as CSV.
"""

import io
import logging
import os
import time
from typing import Any, Dict, List, Optional
import pandas as pd
from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.cards import CARDS
from app.config import settings
from app.services.alert_ledger import alert_ledger
from app.services.concurrency import run_export_task, run_parse_task
from app.services.data_provider import get_data_provider
from app.services.headers import add_headers, iter_csv_chunks, to_xlsx_buffer
from app.services.report_engine import report_engine
from app.services.task1 import get_available_dates, get_card_date_info, run_task1_tms_atm
from app.store import session_store
from app.uploads import read_limited_body

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/task1", tags=["task1"])


def _validate_session(x_session_id: Optional[str]):
    """Verify session is provided, active, and unexpired."""
    if not x_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Session-Id header.",
        )
    session = session_store.get_session(x_session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or not found. Please re-upload or re-select your file.",
        )
    return session


def _parse_workbook_bytes(file_bytes: bytes, card_key: str) -> pd.DataFrame:
    """Parse workbook bytes into DataFrame, applying standard headers if headerless."""
    key = card_key.lower().strip()
    # First try reading row 0 to check if it already contains headers
    buf = io.BytesIO(file_bytes)
    df_first = pd.read_excel(buf, nrows=5, header=None, engine="calamine")
    
    # Check if row 0 has expected column names
    expected = CARDS[key].expected_columns
    first_row_vals = [str(x).strip() for x in df_first.iloc[0].tolist()]
    
    # If first row matches at least 3 expected columns, it already has headers
    matching = sum(1 for val in first_row_vals if val in expected)
    if matching >= min(3, len(expected)):
        buf.seek(0)
        df = pd.read_excel(buf, header=0, dtype=str, engine="calamine")
        # Ensure column names are stripped
        df.columns = [str(c).strip() for c in df.columns]
        return df
    else:
        # Headerless workbook - run through add_headers
        res = add_headers(file_bytes, key)
        if not res["ok"]:
            raise ValueError(res["message"])
        return res["df"]


class DetectRequest(BaseModel):
    target_date: str
    frequency_threshold: Optional[int] = 3
    usd_threshold: Optional[float] = 1500.0


@router.post("/{card_key}/upload")
async def upload_for_task1(
    card_key: str,
    request: Request,
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    x_filename: Optional[str] = Header(None, alias="X-Filename"),
):
    """Upload Excel file strictly in-memory for Task 1 analysis."""
    session = _validate_session(x_session_id)
    key = card_key.lower().strip()
    if key not in CARDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported card type '{card_key}'. Valid cards: {list(CARDS.keys())}",
        )

    if not x_filename or not x_filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .xlsx files are supported. Please provide X-Filename.",
        )

    file_bytes = await read_limited_body(request, max_bytes=settings.MAX_UPLOAD_SIZE_BYTES)

    t0 = time.perf_counter()
    try:
        df = await run_parse_task(_parse_workbook_bytes, file_bytes, key)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Failed to parse workbook: {str(exc)}",
        )
    duration = time.perf_counter() - t0
    logger.info("Task 1 parsed %s (%d bytes) in %.2fs", key, len(file_bytes), duration)

    session.task1["df"] = df
    session.task1["card_key"] = key
    session.task1["filename"] = x_filename

    available_dates = get_available_dates(df, key)
    session.task1["available_dates"] = available_dates

    return {
        "ok": True,
        "card_key": key,
        "filename": x_filename,
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "columns": list(df.columns),
        "available_dates": available_dates,
        "default_date": available_dates[0] if available_dates else None,
        "date_info": get_card_date_info(key),
    }


@router.post("/{card_key}/load-sample")
async def load_sample_dataset(
    card_key: str,
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
):
    """Load local sample dataset in single-user environment for instant verification."""
    session = _validate_session(x_session_id)
    key = card_key.lower().strip()
    if key not in CARDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported card type '{card_key}'.",
        )

    # Search for matching sample file
    candidate_paths = [
        f"data_with_headers/{key}_with_headers_20261028.xlsx",
        f"data/{CARDS[key].label}_spend_20261028.xlsx",
        f"data/{CARDS[key].label}_t2l2_spend_20261028.xlsx",
    ]
    sample_file = None
    for p in candidate_paths:
        if os.path.exists(p):
            sample_file = p
            break

    if not sample_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No local sample dataset found for card '{key}'. Please upload your file.",
        )

    t0 = time.perf_counter()
    with open(sample_file, "rb") as f:
        file_bytes = f.read()

    df = await run_parse_task(_parse_workbook_bytes, file_bytes, key)
    duration = time.perf_counter() - t0
    logger.info("Loaded sample %s (%s) in %.2fs", key, sample_file, duration)

    session.task1["df"] = df
    session.task1["card_key"] = key
    session.task1["filename"] = os.path.basename(sample_file)

    available_dates = get_available_dates(df, key)
    session.task1["available_dates"] = available_dates

    return {
        "ok": True,
        "card_key": key,
        "filename": os.path.basename(sample_file),
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "columns": list(df.columns),
        "available_dates": available_dates,
        "default_date": available_dates[0] if available_dates else None,
        "date_info": get_card_date_info(key),
    }


@router.get("/dates")
async def get_dates(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
):
    """Get list of available dates in the currently active session dataset."""
    session = _validate_session(x_session_id)
    df = session.task1.get("df") if session.task1.get("df") is not None else session.coladd.get("df")
    card_key = session.task1.get("card_key") if session.task1.get("card_key") else session.coladd.get("card_key")

    if df is None or card_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No dataset loaded in session. Please upload a file first.",
        )

    dates = get_available_dates(df, card_key)
    return {
        "card_key": card_key,
        "available_dates": dates,
        "date_info": get_card_date_info(card_key),
    }


@router.post("/{card_key}/detect")
async def detect_alerts(
    card_key: str,
    payload: DetectRequest,
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
):
    """Run Task 1 TMS-ATM Alert Detection for a specific date."""
    session = _validate_session(x_session_id)
    key = card_key.lower().strip()

    df = session.task1.get("df")
    if df is None:
        # Fallback to column-addition df if present
        df = session.coladd.get("df")
        if df is not None:
            session.task1["df"] = df
            session.task1["card_key"] = key

    if df is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No dataset loaded. Please upload a file first.",
        )

    # Run detection
    try:
        res = run_task1_tms_atm(
            df=df,
            card_key=key,
            target_date=payload.target_date,
            frequency_threshold=payload.frequency_threshold or 3,
            usd_threshold=payload.usd_threshold or 1500.0,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Detection error: {str(exc)}",
        )

    # Store results in session for export
    session.task1["target_date"] = payload.target_date
    session.task1["alerts"] = res["alerts"]
    session.task1["flagged_df"] = res["flagged_transactions"]
    session.task1["card_key"] = key

    # Prepare preview rows (up to 200 rows for UI table)
    flagged_df = res["flagged_transactions"]
    preview_rows = flagged_df.head(200).fillna("").to_dict(orient="records")

    return {
        "ok": True,
        "card_key": key,
        "target_date": payload.target_date,
        "total_atm_transactions": res["total_atm_transactions"],
        "flagged_individuals_count": res["flagged_individuals_count"],
        "alerts": res["alerts"],
        "total_flagged_transactions": len(flagged_df),
        "columns": list(flagged_df.columns),
        "preview_rows": preview_rows,
        "date_info": get_card_date_info(key),
    }


def _resolve_account_column(df: pd.DataFrame, card_key: str) -> Optional[str]:
    """Determine individual account column name present in DataFrame."""
    key = card_key.lower().strip()
    if key == "visa" and "spacct" in df.columns:
        return "spacct"
    elif key == "pinelabs" and "Wallet Number" in df.columns:
        return "Wallet Number"
    elif key == "vegapay" and "Account Number" in df.columns:
        return "Account Number"
    for candidate in ("spacct", "Wallet Number", "Account Number", "Customer ID"):
        if candidate in df.columns:
            return candidate
    return None


@router.get("/export-csv")
async def export_flagged_csv(
    account_number: Optional[str] = Query(None, description="Optional account number to export single individual"),
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
):
    """Stream unmodified transactions of flagged individuals as CSV."""
    session = _validate_session(x_session_id)
    flagged_df = session.task1.get("flagged_df")
    if flagged_df is None or len(flagged_df) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No flagged transactions available to export. Run detection first.",
        )

    card_key = session.task1.get("card_key", "card")
    target_date = session.task1.get("target_date", "date")

    df_to_export = flagged_df
    if account_number and account_number.strip():
        acct_col = _resolve_account_column(flagged_df, card_key)
        if acct_col:
            df_to_export = flagged_df[flagged_df[acct_col].astype(str).str.strip() == account_number.strip()]
        if len(df_to_export) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No transactions found for individual '{account_number}'.",
            )
        filename = f"{card_key}_tms_atm_{account_number.strip()}_{target_date}.csv"
    else:
        filename = f"{card_key}_tms_atm_flagged_{target_date}.csv"

    generator = iter_csv_chunks(df_to_export, chunk_size=10000)
    return StreamingResponse(
        generator,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/export-excel")
async def export_flagged_excel(
    account_number: Optional[str] = Query(None, description="Optional account number to export single individual"),
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
):
    """Export unmodified transactions of flagged individuals as in-memory Excel."""
    session = _validate_session(x_session_id)
    flagged_df = session.task1.get("flagged_df")
    if flagged_df is None or len(flagged_df) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No flagged transactions available to export. Run detection first.",
        )

    card_key = session.task1.get("card_key", "card")
    target_date = session.task1.get("target_date", "date")

    df_to_export = flagged_df
    if account_number and account_number.strip():
        acct_col = _resolve_account_column(flagged_df, card_key)
        if acct_col:
            df_to_export = flagged_df[flagged_df[acct_col].astype(str).str.strip() == account_number.strip()]
        if len(df_to_export) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No transactions found for individual '{account_number}'.",
            )
        filename = f"{card_key}_tms_atm_{account_number.strip()}_{target_date}.xlsx"
    else:
        filename = f"{card_key}_tms_atm_flagged_{target_date}.xlsx"

    buf = await run_export_task(to_xlsx_buffer, df_to_export)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/export-alerts-csv")
async def export_alerts_csv(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
):
    """Download alert summary report as CSV."""
    session = _validate_session(x_session_id)
    alerts = session.task1.get("alerts")
    if not alerts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No alert records available to export. Run detection first.",
        )

    card_key = session.task1.get("card_key", "card")
    target_date = session.task1.get("target_date", "date")
    filename = f"{card_key}_tms_atm_alerts_summary_{target_date}.csv"

    df_alerts = pd.DataFrame(alerts)
    generator = iter_csv_chunks(df_alerts, chunk_size=5000)
    return StreamingResponse(
        generator,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "X-Content-Type-Options": "nosniff",
        },
    )


# =============================================================================
# Automated Daily Reports & Cumulative Dossier Endpoints
# =============================================================================

class RunBatchRequest(BaseModel):
    target_date: Optional[str] = None
    cards: Optional[List[str]] = None


@router.get("/automated/overview")
async def get_automated_overview():
    """Retrieve status of automated daily reports, cumulative dossiers, and ledger."""
    yesterday = report_engine.get_yesterday_date()
    provider = get_data_provider()

    # List daily files with metadata
    day_files = []
    if os.path.exists(settings.DAY_OUTPUT_DIR):
        for fname in sorted(os.listdir(settings.DAY_OUTPUT_DIR), reverse=True):
            if fname.endswith(".xlsx") and fname.startswith("daily_report_"):
                meta = report_engine.get_report_metadata(fname)
                day_files.append(meta)

    # List cumulative files
    cum_files = []
    if os.path.exists(settings.CUMULATIVE_OUTPUT_DIR):
        for fname in sorted(os.listdir(settings.CUMULATIVE_OUTPUT_DIR), reverse=True):
            if fname.endswith(".xlsx") and fname.startswith("cumulative_"):
                parts = fname[:-5].split("_")
                card = parts[1] if len(parts) >= 4 else "UNKNOWN"
                acct = parts[2] if len(parts) >= 4 else ""
                dt = parts[3] if len(parts) >= 4 else ""
                fpath = os.path.join(settings.CUMULATIVE_OUTPUT_DIR, fname)
                stat = os.stat(fpath)
                cum_files.append({
                    "filename": fname,
                    "card": card.upper(),
                    "account_number": acct,
                    "date": dt,
                    "size_bytes": stat.st_size,
                    "modified_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
                })

    # Check yesterday's reports status per card
    yesterday_status = {}
    total_y_tx = 0
    total_y_indiv = 0
    total_y_usd = 0.0

    for card in ("visa", "pinelabs", "vegapay"):
        expected_name = f"daily_report_{card}_{yesterday}.xlsx"
        exists = os.path.exists(os.path.join(settings.DAY_OUTPUT_DIR, expected_name))
        if exists:
            meta = report_engine.get_report_metadata(expected_name)
            yesterday_status[card] = {
                "expected_file": expected_name,
                "generated": True,
                "flagged_individuals_count": meta.get("flagged_individuals_count", 0),
                "flagged_transactions_count": meta.get("flagged_transactions_count", 0),
                "total_usd_volume": meta.get("total_usd_volume", 0.0),
                "is_clean": meta.get("is_clean", True),
                "alerts": meta.get("alerts", []),
                "size_bytes": meta.get("size_bytes", 0),
                "generated_at": meta.get("generated_at", ""),
            }
            total_y_tx += meta.get("flagged_transactions_count", 0)
            total_y_indiv += meta.get("flagged_individuals_count", 0)
            total_y_usd += meta.get("total_usd_volume", 0.0)
        else:
            yesterday_status[card] = {
                "expected_file": expected_name,
                "generated": False,
                "flagged_individuals_count": 0,
                "flagged_transactions_count": 0,
                "total_usd_volume": 0.0,
                "is_clean": True,
                "alerts": [],
                "size_bytes": 0,
                "generated_at": "",
            }

    available_dates = {}
    for card in ("visa", "pinelabs", "vegapay"):
        available_dates[card] = provider.get_available_dates(card)[:10]

    # Calculate current month stats (e.g. 2026-11)
    curr_month_prefix = yesterday[:7] if len(yesterday) >= 7 else "2026-11"
    curr_month_tx = 0
    curr_month_indiv_set = set()
    for item in day_files:
        dt = item.get("date", "")
        if dt.startswith(curr_month_prefix):
            curr_month_tx += item.get("flagged_transactions_count", 0)
            for a in item.get("alerts", []):
                curr_month_indiv_set.add(f"{item.get('card')}:{a.get('account_number')}")

    return {
        "status": "ok",
        "yesterday_date": yesterday,
        "yesterday_totals": {
            "total_flagged_transactions": total_y_tx,
            "total_flagged_individuals": total_y_indiv,
            "total_usd_volume": round(total_y_usd, 2),
        },
        "monthly_summary": {
            "current_month": curr_month_prefix,
            "flagged_transactions_count": curr_month_tx,
            "flagged_individuals_count": len(curr_month_indiv_set),
            "historical_query_ready": settings.DATA_SOURCE_PROVIDER == "sql",
        },
        "timezone": settings.REPORT_TIMEZONE,
        "delay_minutes": settings.DAILY_RUN_DELAY_MINUTES,
        "data_provider": settings.DATA_SOURCE_PROVIDER,
        "cumulative_threshold": settings.CUMULATIVE_ALERT_THRESHOLD,
        "yesterday_status": yesterday_status,
        "daily_reports_count": len(day_files),
        "cumulative_reports_count": len(cum_files),
        "recent_daily_reports": day_files[:25],
        "recent_cumulative_reports": cum_files[:25],
        "available_dates_sample": available_dates,
        "ledger_summary": alert_ledger.get_ledger_summary(),
    }


@router.get("/automated/report-details/{filename}")
async def get_report_details_endpoint(filename: str):
    """Retrieve structured alert rows and sample flagged transactions for on-top modal view."""
    safe_name = os.path.basename(filename)
    details = report_engine.get_report_details(safe_name)
    if "error" in details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report '{safe_name}' not found.",
        )
    return details


@router.post("/automated/run-batch")
async def trigger_automated_batch(payload: RunBatchRequest):
    """Manually trigger daily batch execution on-demand for any date."""
    try:
        result = report_engine.run_daily_batch(
            target_date=payload.target_date,
            cards=payload.cards,
        )
        return result
    except Exception as exc:
        logger.exception("Error running batch: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch execution failed: {str(exc)}",
        )


@router.get("/automated/download/daily/{filename}")
async def download_daily_report(filename: str):
    """Download generated daily report file."""
    safe_name = os.path.basename(filename)
    file_path = os.path.join(settings.DAY_OUTPUT_DIR, safe_name)
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Daily report '{safe_name}' not found.",
        )

    def file_iterator():
        with open(file_path, "rb") as f:
            while chunk := f.read(64 * 1024):
                yield chunk

    return StreamingResponse(
        file_iterator(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/automated/download/cumulative/{filename}")
async def download_cumulative_report(filename: str):
    """Download generated cumulative investigation dossier."""
    safe_name = os.path.basename(filename)
    file_path = os.path.join(settings.CUMULATIVE_OUTPUT_DIR, safe_name)
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cumulative report '{safe_name}' not found.",
        )

    def file_iterator():
        with open(file_path, "rb") as f:
            while chunk := f.read(64 * 1024):
                yield chunk

    return StreamingResponse(
        file_iterator(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/automated/ledger")
async def get_full_alert_ledger():
    """Retrieve raw alert ledger state."""
    return alert_ledger.load()


