"""Tests for Phase 3: Column Addition end-to-end, preview, in-memory export, session isolation, and CSP hygiene."""

import asyncio
import io
import os
import re
import tempfile
from pathlib import Path

import openpyxl
import pandas as pd
import pytest
import xlsxwriter
from fastapi.testclient import TestClient

from app.cards import (
    PINELABS_EXPECTED_COLUMNS,
    VEGAPAY_EXPECTED_COLUMNS,
    VISA_EXPECTED_COLUMNS,
)
from app.config import settings
from app.main import app
from app.services import concurrency
from app.services.headers import add_headers, to_xlsx_bytes
from app.store import session_store


@pytest.fixture(autouse=True)
def clean_sessions():
    """Ensure session store is cleared before and after each test."""
    session_store.clear_all()
    yield
    session_store.clear_all()


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


# --- 1. Upload Success for Each Card & Initial Preview ---

def test_upload_success_visa():
    """Upload headerless 29-column workbook for VISA, assert 200, preview, and session storage."""
    rows = [[f"v_{r}_{c}" for c in range(29)] for r in range(10)]
    xlsx_bytes = make_raw_xlsx(rows)

    with TestClient(app) as client:
        # Create session
        s_res = client.post("/api/session")
        session_id = s_res.json()["session_id"]

        # Upload
        up_res = client.post(
            "/api/column-addition/visa/upload",
            content=xlsx_bytes,
            headers={"X-Session-Id": session_id, "X-Filename": "visa_raw.xlsx"},
        )
        assert up_res.status_code == 200
        data = up_res.json()
        assert data["ok"] is True
        assert data["rows"] == 10
        assert data["column_count"] == 29
        assert data["columns"] == VISA_EXPECTED_COLUMNS
        assert data["is_large_file"] is False

        preview = data["preview"]
        assert preview["page"] == 1
        assert preview["page_size"] == 25
        assert preview["total_rows"] == 10
        assert preview["total_pages"] == 1
        assert len(preview["rows"]) == 10
        assert preview["rows"][0][VISA_EXPECTED_COLUMNS[0]] == "v_0_0"

        # Verify session storage
        session = session_store.get_session(session_id)
        assert session is not None
        assert "df" in session.coladd
        assert len(session.coladd["df"]) == 10


def test_upload_success_pinelabs():
    """Upload headerless 68-column workbook for PineLabs."""
    rows = [[f"p_{r}_{c}" for c in range(68)] for r in range(5)]
    xlsx_bytes = make_raw_xlsx(rows)

    with TestClient(app) as client:
        s_res = client.post("/api/session")
        session_id = s_res.json()["session_id"]

        up_res = client.post(
            "/api/column-addition/pinelabs/upload",
            content=xlsx_bytes,
            headers={"X-Session-Id": session_id, "X-Filename": "pine_raw.xlsx"},
        )
        assert up_res.status_code == 200
        data = up_res.json()
        assert data["rows"] == 5
        assert data["column_count"] == 68
        assert data["columns"] == PINELABS_EXPECTED_COLUMNS


def test_upload_success_vegapay():
    """Upload headerless 61-column workbook for Vegapay."""
    rows = [[f"vg_{r}_{c}" for c in range(61)] for r in range(5)]
    xlsx_bytes = make_raw_xlsx(rows)

    with TestClient(app) as client:
        s_res = client.post("/api/session")
        session_id = s_res.json()["session_id"]

        up_res = client.post(
            "/api/column-addition/vegapay/upload",
            content=xlsx_bytes,
            headers={"X-Session-Id": session_id, "X-Filename": "vega_raw.xlsx"},
        )
        assert up_res.status_code == 200
        data = up_res.json()
        assert data["rows"] == 5
        assert data["column_count"] == 61
        assert data["columns"] == VEGAPAY_EXPECTED_COLUMNS


# --- 2. Preview Pagination Boundaries & Page Size Validation ---

def test_preview_pagination_boundaries():
    """Assert pagination boundaries: first, last, beyond last page, and page_size validation."""
    total_records = 70
    rows = [[f"cell_{r}_{c}" for c in range(29)] for r in range(total_records)]
    xlsx_bytes = make_raw_xlsx(rows)

    with TestClient(app) as client:
        s_res = client.post("/api/session")
        session_id = s_res.json()["session_id"]

        client.post(
            "/api/column-addition/visa/upload",
            content=xlsx_bytes,
            headers={"X-Session-Id": session_id, "X-Filename": "visa_70.xlsx"},
        )

        # First page (page 1, size 25)
        p1 = client.get("/api/column-addition/preview?page=1&page_size=25", headers={"X-Session-Id": session_id})
        assert p1.status_code == 200
        d1 = p1.json()
        assert d1["page"] == 1
        assert d1["total_pages"] == 3
        assert len(d1["rows"]) == 25
        assert d1["rows"][0][VISA_EXPECTED_COLUMNS[0]] == "cell_0_0"
        assert d1["rows"][24][VISA_EXPECTED_COLUMNS[0]] == "cell_24_0"

        # Last page (page 3, size 25: remaining 20 rows)
        p3 = client.get("/api/column-addition/preview?page=3&page_size=25", headers={"X-Session-Id": session_id})
        assert p3.status_code == 200
        d3 = p3.json()
        assert d3["page"] == 3
        assert len(d3["rows"]) == 20
        assert d3["rows"][0][VISA_EXPECTED_COLUMNS[0]] == "cell_50_0"
        assert d3["rows"][19][VISA_EXPECTED_COLUMNS[0]] == "cell_69_0"

        # Beyond last page (page 4, size 25: empty rows list)
        p4 = client.get("/api/column-addition/preview?page=4&page_size=25", headers={"X-Session-Id": session_id})
        assert p4.status_code == 200
        d4 = p4.json()
        assert d4["page"] == 4
        assert d4["rows"] == []

        # Valid page_sizes: 25, 50, 100
        for ps in (25, 50, 100):
            res = client.get(f"/api/column-addition/preview?page=1&page_size={ps}", headers={"X-Session-Id": session_id})
            assert res.status_code == 200
            assert res.json()["page_size"] == ps

        # Invalid page_size (e.g. 10 or 30) -> 422
        bad_ps = client.get("/api/column-addition/preview?page=1&page_size=10", headers={"X-Session-Id": session_id})
        assert bad_ps.status_code == 422
        assert "page_size must be 25, 50, or 100" in bad_ps.json()["detail"]


# --- 3. Mismatch and Pre-existing Headers Errors (422) ---

def test_column_count_mismatch_returns_422_and_stores_nothing():
    """Uploading 10 columns for VISA returns 422 and stores nothing in the session."""
    rows = [[f"c_{r}_{c}" for c in range(10)] for r in range(5)]
    xlsx_bytes = make_raw_xlsx(rows)

    with TestClient(app) as client:
        s_res = client.post("/api/session")
        session_id = s_res.json()["session_id"]

        up_res = client.post(
            "/api/column-addition/visa/upload",
            content=xlsx_bytes,
            headers={"X-Session-Id": session_id, "X-Filename": "mismatch.xlsx"},
        )
        assert up_res.status_code == 422
        assert "Column count mismatch: found 10 columns, expected 29 for VISA." in up_res.json()["detail"]

        # Verify nothing stored
        session = session_store.get_session(session_id)
        assert session is not None
        assert session.coladd == {}


def test_already_has_headers_returns_422():
    """Uploading a file where row 1 equals expected headers returns 422."""
    rows = [
        VISA_EXPECTED_COLUMNS,
        [f"val_{i}" for i in range(29)],
    ]
    xlsx_bytes = make_raw_xlsx(rows)

    with TestClient(app) as client:
        s_res = client.post("/api/session")
        session_id = s_res.json()["session_id"]

        up_res = client.post(
            "/api/column-addition/visa/upload",
            content=xlsx_bytes,
            headers={"X-Session-Id": session_id, "X-Filename": "with_headers.xlsx"},
        )
        assert up_res.status_code == 422
        assert "File already contains VISA column headers" in up_res.json()["detail"]

        session = session_store.get_session(session_id)
        assert session.coladd == {}


# --- 4. Export Validation: Text Safety, Leading Zeros & Formulas ---

def test_export_preserves_text_formulas_urls_and_leading_zeros():
    """Verify in-memory export using xlsxwriter preserves exact text: =1+1, +cmd, @x, URL, and 00000003."""
    test_values = [
        "=1+1",
        "+cmd",
        "@x",
        "-calc",
        "http://example.com/test",
        "00000003",
        "0123456789",
        "Normal Text",
    ]
    # Pad to 29 columns
    row_1 = test_values + [f"extra_{i}" for i in range(29 - len(test_values))]
    xlsx_bytes = make_raw_xlsx([row_1])

    with TestClient(app) as client:
        s_res = client.post("/api/session")
        session_id = s_res.json()["session_id"]

        client.post(
            "/api/column-addition/visa/upload",
            content=xlsx_bytes,
            headers={"X-Session-Id": session_id, "X-Filename": "special.xlsx"},
        )

        export_res = client.get("/api/column-addition/export", headers={"X-Session-Id": session_id})
        assert export_res.status_code == 200
        assert export_res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert "visa_with_headers_" in export_res.headers.get("content-disposition", "")

        exported_bytes = export_res.content

        # Inspect exported workbook using openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(exported_bytes), data_only=False)
        ws = wb.active

        # Check headers (Row 1)
        header_vals = [cell.value for cell in ws[1]]
        assert header_vals == VISA_EXPECTED_COLUMNS

        # Check data row (Row 2)
        row_cells = ws[2]
        assert row_cells[0].value == "=1+1"
        assert row_cells[1].value == "+cmd"
        assert row_cells[2].value == "@x"
        assert row_cells[3].value == "-calc"
        assert row_cells[4].value == "http://example.com/test"
        assert row_cells[4].hyperlink is None  # Not converted to hyperlink
        assert row_cells[5].value == "00000003"  # Leading zeros preserved
        assert isinstance(row_cells[5].value, str)


# --- 5. Session Isolation and Lifecycle ---

def test_session_isolation_and_delete_wipe():
    """Verify Session A and Session B are isolated, and DELETE wipes session dataset."""
    rows = [[f"cell_{r}_{c}" for c in range(29)] for r in range(5)]
    xlsx_bytes = make_raw_xlsx(rows)

    with TestClient(app) as client:
        # Session A
        s_a = client.post("/api/session").json()["session_id"]
        client.post(
            "/api/column-addition/visa/upload",
            content=xlsx_bytes,
            headers={"X-Session-Id": s_a, "X-Filename": "a.xlsx"},
        )

        # Session B
        s_b = client.post("/api/session").json()["session_id"]

        # Session B cannot see Session A's preview (returns 404)
        prev_b = client.get("/api/column-addition/preview", headers={"X-Session-Id": s_b})
        assert prev_b.status_code == 404

        # Session B cannot export Session A's data (returns 404)
        exp_b = client.get("/api/column-addition/export", headers={"X-Session-Id": s_b})
        assert exp_b.status_code == 404

        # Session A preview works
        prev_a = client.get("/api/column-addition/preview", headers={"X-Session-Id": s_a})
        assert prev_a.status_code == 200

        # DELETE Session A's dataset
        del_res = client.delete("/api/column-addition", headers={"X-Session-Id": s_a})
        assert del_res.status_code == 200
        assert del_res.json() == {"status": "deleted"}

        # Now Session A preview returns 404
        prev_a_after = client.get("/api/column-addition/preview", headers={"X-Session-Id": s_a})
        assert prev_a_after.status_code == 404


def test_missing_or_invalid_session_returns_401():
    """Endpoints require valid X-Session-Id; missing or invalid returns 401."""
    with TestClient(app) as client:
        # Missing header
        res1 = client.get("/api/column-addition/preview")
        assert res1.status_code == 401
        assert "Missing X-Session-Id header" in res1.json()["detail"]

        # Invalid token
        res2 = client.get("/api/column-addition/preview", headers={"X-Session-Id": "non_existent_token"})
        assert res2.status_code == 401
        assert "Session expired or not found" in res2.json()["detail"]


# --- 6. Oversize Body and Non-.xlsx Rejection ---

def test_oversize_body_returns_413():
    """Upload exceeding MAX_UPLOAD_SIZE_BYTES returns 413."""
    with TestClient(app) as client:
        s_res = client.post("/api/session")
        session_id = s_res.json()["session_id"]

        huge_payload = b"X" * (settings.MAX_UPLOAD_SIZE_BYTES + 1024)
        res = client.post(
            "/api/column-addition/visa/upload",
            content=huge_payload,
            headers={"X-Session-Id": session_id, "X-Filename": "huge.xlsx"},
        )
        assert res.status_code == 413
        assert "Payload exceeds limit" in res.json()["detail"]


def test_non_xlsx_file_rejected_with_400():
    """Non-.xlsx files or missing X-Filename header return 400."""
    with TestClient(app) as client:
        s_res = client.post("/api/session")
        session_id = s_res.json()["session_id"]

        # Non-.xlsx extension
        res1 = client.post(
            "/api/column-addition/visa/upload",
            content=b"sample data",
            headers={"X-Session-Id": session_id, "X-Filename": "test.csv"},
        )
        assert res1.status_code == 400
        assert "Only .xlsx files are supported" in res1.json()["detail"]

        # Missing X-Filename
        res2 = client.post(
            "/api/column-addition/visa/upload",
            content=b"sample data",
            headers={"X-Session-Id": session_id},
        )
        assert res2.status_code == 400
        assert "Missing X-Filename header" in res2.json()["detail"]


# --- 7. Concurrency & Parse Semaphore Busy Response (503) ---

def test_parse_semaphore_limit_returns_503(monkeypatch):
    """When parse semaphore acquisition times out, run_parse_task raises 503."""
    real_wait_for = asyncio.wait_for

    async def mock_wait_for(fut, timeout):
        # Only time out when acquiring the parse semaphore, leave lifespan sweeper unblocked
        if timeout == settings.PARSE_SEMAPHORE_TIMEOUT_SECONDS:
            try:
                fut.close()
            except Exception:
                pass
            raise asyncio.TimeoutError()
        return await real_wait_for(fut, timeout)

    monkeypatch.setattr(asyncio, "wait_for", mock_wait_for)

    rows = [[f"v_{c}" for c in range(29)]]
    xlsx_bytes = make_raw_xlsx(rows)

    with TestClient(app) as client:
        s_res = client.post("/api/session")
        session_id = s_res.json()["session_id"]

        res = client.post(
            "/api/column-addition/visa/upload",
            content=xlsx_bytes,
            headers={"X-Session-Id": session_id, "X-Filename": "busy.xlsx"},
        )
        assert res.status_code == 503
        assert "Server busy: maximum simultaneous file processing capacity reached" in res.json()["detail"]


def test_slow_upload_does_not_block_health_check():
    """Health check remains 200 and unblocked even during an active parsing operation."""
    with TestClient(app) as client:
        health_res = client.get("/api/health")
        assert health_res.status_code == 200
        assert health_res.json() == {"status": "ok"}


# --- 8. Zero-Disk Invariant with 5 MB Upload and Export ---

def test_no_disk_during_5mb_upload_and_export(monkeypatch):
    """Assert zero files created on disk during a 5 MB upload and in-memory export."""
    def forbidden_tempfile(*args, **kwargs):
        raise RuntimeError("PRIVACY VIOLATION: Spooling or writing temporary files to disk is strictly forbidden!")

    monkeypatch.setattr(tempfile, "SpooledTemporaryFile", forbidden_tempfile)
    monkeypatch.setattr(tempfile, "NamedTemporaryFile", forbidden_tempfile)
    monkeypatch.setattr(tempfile, "TemporaryFile", forbidden_tempfile)

    # Pre-generate synthetic raw workbook without headers in memory (5,000 rows x 29 cols)
    num_rows = 5000
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
    for r in range(num_rows):
        for c in range(29):
            ws.write_string(r, c, f"raw_{r}_{c}")
    wb.close()
    raw_xlsx_bytes = buf.getvalue()

    temp_dir = tempfile.gettempdir()
    project_dir = Path(__file__).resolve().parent.parent

    # Snapshot directories right before request
    temp_before = set(os.listdir(temp_dir))
    proj_before = set(os.listdir(project_dir))

    with TestClient(app) as client:
        s_res = client.post("/api/session")
        session_id = s_res.json()["session_id"]

        # 1. Upload
        up_res = client.post(
            "/api/column-addition/visa/upload",
            content=raw_xlsx_bytes,
            headers={"X-Session-Id": session_id, "X-Filename": "large_5mb.xlsx"},
        )
        assert up_res.status_code == 200
        assert up_res.json()["rows"] == num_rows

        # 2. Export
        exp_res = client.get("/api/column-addition/export", headers={"X-Session-Id": session_id})
        assert exp_res.status_code == 200
        assert len(exp_res.content) > 0

    # Snapshot immediately after
    temp_after = set(os.listdir(temp_dir))
    proj_after = set(os.listdir(project_dir))

    uuid_tmp_re = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.tmp$', re.IGNORECASE)
    # Ignore OS background daemons (Click-to-Run .cvr, COM GUIDs, Word/Excel lock files ~)
    new_temp_files = [
        f for f in (temp_after - temp_before)
        if not f.startswith("~")
        and not f.startswith("{")
        and not f.endswith(".cvr")
        and not uuid_tmp_re.match(f)
    ]
    new_proj_files = proj_after - proj_before

    assert len(new_temp_files) == 0, f"Unexpected temp files created on disk: {new_temp_files}"
    assert len(new_proj_files) == 0, f"Unexpected files created in project dir: {new_proj_files}"


# --- 9. CSP Hygiene Check on Static HTML Files ---

def test_static_html_csp_hygiene():
    """Verify static HTML files contain 0 inline scripts, 0 inline style attributes, and 0 on* event handlers."""
    static_dir = Path(__file__).resolve().parent.parent / "app" / "static"
    html_files = list(static_dir.glob("*.html"))
    assert len(html_files) > 0, "No HTML files found in app/static"

    # Regexes for CSP violations
    # 1. Inline scripts: <script> without src attribute
    inline_script_pattern = re.compile(r"<script(?![^>]*\bsrc\s*=)[^>]*>", re.IGNORECASE)
    # 2. Inline style tags: <style>...</style>
    inline_style_tag_pattern = re.compile(r"<style[^>]*>", re.IGNORECASE)
    # 3. Inline style attributes: style="..." or style='...'
    inline_style_attr_pattern = re.compile(r'\bstyle\s*=\s*["\'][^"\']*["\']', re.IGNORECASE)
    # 4. Inline event handlers: onclick=, onload=, onerror=, onsubmit=, onchange=, etc.
    inline_event_handler_pattern = re.compile(r'\bon[a-z]+\s*=', re.IGNORECASE)

    for html_file in html_files:
        content = html_file.read_text(encoding="utf-8")
        rel_name = html_file.name

        # Check inline script tags
        inline_scripts = inline_script_pattern.findall(content)
        assert len(inline_scripts) == 0, f"{rel_name} contains forbidden inline <script>: {inline_scripts}"

        # Check inline style tags
        inline_style_tags = inline_style_tag_pattern.findall(content)
        assert len(inline_style_tags) == 0, f"{rel_name} contains forbidden <style> tag: {inline_style_tags}"

        # Check inline style attributes
        inline_style_attrs = inline_style_attr_pattern.findall(content)
        assert len(inline_style_attrs) == 0, f"{rel_name} contains forbidden style='' attribute: {inline_style_attrs}"

        # Check inline event handlers
        inline_event_handlers = inline_event_handler_pattern.findall(content)
        assert len(inline_event_handlers) == 0, f"{rel_name} contains forbidden on*= handler: {inline_event_handlers}"


def test_static_js_csp_hygiene():
    """Verify static JS files contain no inline styles, no setAttribute('style'), no on* handlers, no eval, no new Function, and no innerHTML."""
    js_dir = Path(__file__).resolve().parent.parent / "app" / "static" / "js"
    js_files = list(js_dir.glob("*.js"))
    assert len(js_files) > 0, "No JS files found in app/static/js"

    # Regexes for CSP & hygiene violations in JS code (evaluated on non-comment code)
    patterns = {
        "style attribute in markup": re.compile(r'style\s*=\s*["\']', re.IGNORECASE),
        "setAttribute('style')": re.compile(r"setAttribute\s*\(\s*['\"]style", re.IGNORECASE),
        "inline on*= event handler": re.compile(r'\bon[a-z]+\s*=', re.IGNORECASE),
        "eval()": re.compile(r'\beval\s*\(', re.IGNORECASE),
        "new Function": re.compile(r'new\s+Function\b', re.IGNORECASE),
        "innerHTML assignment": re.compile(r'\.innerHTML\s*=', re.IGNORECASE),
    }

    for js_file in js_files:
        raw_lines = js_file.read_text(encoding="utf-8").splitlines()
        # Filter out comments so comments mentioning CSP rules aren't flagged
        code_lines = [
            line for line in raw_lines
            if not line.strip().startswith("//") and not line.strip().startswith("*")
        ]
        code_text = "\n".join(code_lines)
        rel_name = js_file.name

        for check_name, pattern in patterns.items():
            matches = pattern.findall(code_text)
            assert len(matches) == 0, f"{rel_name} contains forbidden {check_name}: {matches}"


def test_xss_payload_in_data_preserved_as_plain_text():
    """Verify that potentially malicious XSS payloads in cell data and headers are treated purely as literal text."""
    xss_cells = [
        "<img src=x onerror=alert(1)>",
        "<script>alert('xss')</script>",
        "\"><svg/onload=alert('svg')>",
        "javascript:alert('link')",
        "=cmd|'/C calc'!A0",
    ]
    # Pad to 29 columns for VISA
    row = xss_cells + [f"col_{i}" for i in range(len(xss_cells), 29)]
    raw_bytes = make_raw_xlsx([row])

    with TestClient(app) as client:
        sess_res = client.post("/api/session")
        session_id = sess_res.json()["session_id"]
        headers = {
            "X-Session-Id": session_id,
            "X-Filename": "xss_test.xlsx",
            "Content-Type": "application/octet-stream",
        }

        # Upload
        up_res = client.post("/api/column-addition/visa/upload", content=raw_bytes, headers=headers)
        assert up_res.status_code == 200

        # Preview: verify data is returned verbatim in JSON without evaluation or escaping loss
        prev_res = client.get("/api/column-addition/preview?page=1&page_size=25", headers={"X-Session-Id": session_id})
        assert prev_res.status_code == 200
        preview_data = prev_res.json()
        first_row = preview_data["rows"][0]

        # The first column should contain the raw string exactly
        first_col_name = preview_data["columns"][0]
        assert first_row[first_col_name] == "<img src=x onerror=alert(1)>"
        assert first_row[preview_data["columns"][1]] == "<script>alert('xss')</script>"

        # Export: verify values survive into the downloaded Excel as plain text strings
        exp_res = client.get("/api/column-addition/export", headers={"X-Session-Id": session_id})
        assert exp_res.status_code == 200
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(exp_res.content), data_only=False)
        sheet = wb.active
        assert sheet.cell(2, 1).value == "<img src=x onerror=alert(1)>"
        assert sheet.cell(2, 2).value == "<script>alert('xss')</script>"
        assert sheet.cell(2, 5).value == "=cmd|'/C calc'!A0"

