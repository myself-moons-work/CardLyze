"""Tests for large export optimizations, streaming CSV export, fidelity, and local configuration limits."""

import csv
import io
import os
import tempfile
from unittest.mock import patch
import openpyxl
import pandas as pd
import pytest
import xlsxwriter
from fastapi.testclient import TestClient

from app.cards import get_card_config
from app.config import Settings, settings
from app.main import app, check_host_binding
from app.services.headers import iter_csv_chunks, to_xlsx_buffer, to_xlsx_bytes
from app.store import session_store

VISA_EXPECTED_COLUMNS = list(get_card_config("visa").expected_columns)


@pytest.fixture(autouse=True)
def clean_sessions():
    """Ensure session store is clean before and after each test."""
    with session_store._lock:
        session_store._sessions.clear()
    yield
    with session_store._lock:
        session_store._sessions.clear()


def make_raw_xlsx(rows: list) -> bytes:
    """Create an in-memory .xlsx file without headers using xlsxwriter in text-safe mode."""
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(
        buf,
        {
            "in_memory": True,
            "strings_to_formulas": False,
            "strings_to_urls": False,
            "strings_to_numbers": False,
        },
    )
    ws = wb.add_worksheet("Sheet1")
    for r_idx, row in enumerate(rows):
        for c_idx, val in enumerate(row):
            ws.write_string(r_idx, c_idx, str(val))
    wb.close()
    return buf.getvalue()


# --- 1. CSV Export Content & Round-Trip Fidelity ---

def test_csv_export_fidelity_roundtrip():
    """Verify CSV export preserves exact values through csv.reader and pd.read_csv:
    - embedded newline
    - quote
    - comma
    - leading zeros
    - formula-like text (=1+1, +cmd, @x, -calc)
    - non-ASCII text
    - empty strings
    """
    test_values = [
        "Line1\nLine2",            # Embedded newline
        'He said "Hello"',          # Embedded quotes
        "a,b,c",                    # Embedded comma
        "00000003",                 # Leading zeros (number-like string)
        "0123456789",               # Leading zero numeric string
        "=1+1",                     # Formula text
        "+cmd",                     # Command prefix
        "@x",                       # At prefix
        "-calc",                    # Minus prefix
        "https://example.com/tx",   # URL
        "Héllo ₹500",               # Non-ASCII UTF-8
        "",                         # Empty string
        "Normal Text",              # Regular string
    ]

    # Pad row to 29 columns matching VISA schema
    full_row = test_values + [f"col_{i}" for i in range(29 - len(test_values))]
    df = pd.DataFrame([full_row], columns=VISA_EXPECTED_COLUMNS)

    # Stream chunks
    chunks = list(iter_csv_chunks(df, chunk_size=20_000))
    assert len(chunks) >= 1
    raw_csv_bytes = b"".join(chunks)

    # 1. Assert UTF-8 BOM is present at the very beginning
    assert raw_csv_bytes.startswith(b"\xef\xbb\xbf")

    # 2. Decode UTF-8 (handling BOM)
    csv_text = raw_csv_bytes.decode("utf-8-sig")

    # 3. Round-trip through standard library csv.reader
    reader = list(csv.reader(io.StringIO(csv_text), lineterminator="\r\n"))
    assert len(reader) == 2  # Header row + 1 data row
    assert reader[0] == VISA_EXPECTED_COLUMNS

    data_row = reader[1]
    for idx, expected in enumerate(full_row):
        assert data_row[idx] == expected, f"Mismatch at col {idx}: expected {expected!r}, got {data_row[idx]!r}"

    # 4. Round-trip through pandas read_csv(dtype=str, keep_default_na=False)
    roundtrip_df = pd.read_csv(
        io.StringIO(csv_text),
        dtype=str,
        keep_default_na=False,
    )
    assert list(roundtrip_df.columns) == VISA_EXPECTED_COLUMNS
    for col_idx, col_name in enumerate(VISA_EXPECTED_COLUMNS):
        assert roundtrip_df[col_name].iloc[0] == full_row[col_idx]


def test_csv_export_streaming_chunked():
    """Verify that a 50,000-row DataFrame is chunked into multiple chunks and first chunk yields immediately."""
    n_rows = 50_000
    row_pattern = [f"val_{c}" for c in range(29)]
    # Create 50k DataFrame
    df = pd.DataFrame([row_pattern] * n_rows, columns=VISA_EXPECTED_COLUMNS)

    gen = iter_csv_chunks(df, chunk_size=20_000)

    # First chunk is available before generator is exhausted
    first_chunk = next(gen)
    assert first_chunk.startswith(b"\xef\xbb\xbf")
    assert len(first_chunk) > 0

    remaining_chunks = list(gen)
    # Total chunks should be 3 (20k + 20k + 10k)
    assert len(remaining_chunks) == 2
    assert all(not c.startswith(b"\xef\xbb\xbf") for c in remaining_chunks)  # BOM only in first chunk


# --- 2. CSV Export HTTP Endpoint Tests ---

def test_csv_export_endpoint_success():
    """Verify GET /api/column-addition/export-csv returns 200 StreamingResponse with correct headers."""
    rows = [
        ["00000003", "=1+1", "Normal"] + [f"c_{i}" for i in range(26)]
    ]
    raw_bytes = make_raw_xlsx(rows)

    with TestClient(app) as client:
        s_res = client.post("/api/session")
        session_id = s_res.json()["session_id"]

        # Upload
        up_res = client.post(
            "/api/column-addition/visa/upload",
            content=raw_bytes,
            headers={"X-Session-Id": session_id, "X-Filename": "tx.xlsx"},
        )
        assert up_res.status_code == 200

        # Export CSV
        csv_res = client.get(
            "/api/column-addition/export-csv",
            headers={"X-Session-Id": session_id},
        )
        assert csv_res.status_code == 200
        assert "text/csv" in csv_res.headers.get("content-type", "")
        assert "visa_with_headers_" in csv_res.headers.get("content-disposition", "")
        assert csv_res.headers.get("content-disposition", "").endswith('.csv"')

        # Verify body starts with BOM
        assert csv_res.content.startswith(b"\xef\xbb\xbf")
        text = csv_res.content.decode("utf-8-sig")
        assert "00000003" in text
        assert "=1+1" in text


def test_csv_export_session_and_401_rules():
    """Verify 401 on missing session, 401 on expired/invalid session, 404 on no dataset."""
    with TestClient(app) as client:
        # 1. Missing session
        res = client.get("/api/column-addition/export-csv")
        assert res.status_code == 401

        # 2. Invalid session
        res = client.get(
            "/api/column-addition/export-csv",
            headers={"X-Session-Id": "invalid-session-token"},
        )
        assert res.status_code == 401

        # 3. Valid session with no upload
        s_res = client.post("/api/session")
        s_id = s_res.json()["session_id"]
        res = client.get(
            "/api/column-addition/export-csv",
            headers={"X-Session-Id": s_id},
        )
        assert res.status_code == 404


def test_no_disk_during_csv_export():
    """Verify that uploading and streaming CSV export writes 0 files to disk."""
    rows = [[f"cell_{r}_{c}" for c in range(29)] for r in range(100)]
    xlsx_bytes = make_raw_xlsx(rows)

    temp_dir = tempfile.gettempdir()
    initial_files = set(os.listdir(temp_dir))

    with TestClient(app) as client:
        s_id = client.post("/api/session").json()["session_id"]

        client.post(
            "/api/column-addition/visa/upload",
            content=xlsx_bytes,
            headers={"X-Session-Id": s_id, "X-Filename": "sample.xlsx"},
        )

        res = client.get("/api/column-addition/export-csv", headers={"X-Session-Id": s_id})
        assert res.status_code == 200
        assert len(res.content) > 0

    final_files = set(os.listdir(temp_dir))
    new_files = final_files - initial_files
    suspicious = [f for f in new_files if f.endswith((".xlsx", ".csv", ".tmp", ".dat"))]
    assert len(suspicious) == 0, f"Temporary files were written to disk: {suspicious}"


# --- 3. Optimized Excel Export Buffer Tests ---

def test_optimized_xlsx_buffer_preserves_text_exact():
    """Verify to_xlsx_buffer preserves raw text, URLs, formulas, leading zeros, and blanks."""
    test_values = ["=1+1", "+cmd", "@x", "-calc", "http://example.com/tx", "00000003", "", None]
    full_row = test_values + [f"extra_{i}" for i in range(29 - len(test_values))]
    df = pd.DataFrame([full_row], columns=VISA_EXPECTED_COLUMNS)

    buf = to_xlsx_buffer(df)
    assert isinstance(buf, io.BytesIO)
    content = buf.getvalue()
    assert len(content) > 0

    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=False)
    ws = wb.active
    # Row 1 is header
    assert [cell.value for cell in ws[1]] == VISA_EXPECTED_COLUMNS
    # Row 2 is data
    row_cells = ws[2]
    assert row_cells[0].value == "=1+1"
    assert row_cells[1].value == "+cmd"
    assert row_cells[2].value == "@x"
    assert row_cells[3].value == "-calc"
    assert row_cells[4].value == "http://example.com/tx"
    assert row_cells[4].hyperlink is None
    assert row_cells[5].value == "00000003"
    assert row_cells[6].value is None or row_cells[6].value == ""
    assert row_cells[7].value is None


# --- 4. Local Limits & Host Binding Verification ---

def test_local_limits_defaults():
    """Verify default local limits: MAX_SESSIONS=2, MAX_PARALLEL_PARSES=1, MAX_PARALLEL_EXPORTS=1."""
    assert settings.MAX_CONCURRENT_SESSIONS == 2
    assert settings.MAX_CONCURRENT_PARSES == 1
    assert settings.MAX_CONCURRENT_EXPORTS == 1
    assert settings.ALLOW_NON_LOOPBACK is False


def test_session_capacity_limit_default_is_two():
    """Verify default session store capacity limit is 2 (3rd session returns 503)."""
    with TestClient(app) as client:
        r1 = client.post("/api/session")
        assert r1.status_code == 201

        r2 = client.post("/api/session")
        assert r2.status_code == 201

        # 3rd session should exceed default MAX_SESSIONS=2
        r3 = client.post("/api/session")
        assert r3.status_code == 503
        assert "Maximum concurrent sessions reached" in r3.json()["detail"]


def test_non_loopback_host_refusal():
    """Verify application startup check refuses non-loopback hosts unless ALLOW_NON_LOOPBACK is set."""
    # 1. Non-loopback host with ALLOW_NON_LOOPBACK=False -> raises RuntimeError
    with patch("app.main.settings", Settings(HOST="0.0.0.0", ALLOW_NON_LOOPBACK=False)):
        with pytest.raises(RuntimeError, match="Refusing to start on non-loopback host '0.0.0.0'"):
            check_host_binding()

    with patch("app.main.settings", Settings(HOST="192.168.1.50", ALLOW_NON_LOOPBACK=False)):
        with pytest.raises(RuntimeError, match="Refusing to start on non-loopback host '192.168.1.50'"):
            check_host_binding()

    # 2. Loopback hosts -> succeeds
    with patch("app.main.settings", Settings(HOST="127.0.0.1", ALLOW_NON_LOOPBACK=False)):
        check_host_binding()  # No exception

    with patch("app.main.settings", Settings(HOST="localhost", ALLOW_NON_LOOPBACK=False)):
        check_host_binding()  # No exception

    # 3. Non-loopback host with ALLOW_NON_LOOPBACK=True -> succeeds with logged warning
    with patch("app.main.settings", Settings(HOST="0.0.0.0", ALLOW_NON_LOOPBACK=True)):
        check_host_binding()  # No exception
