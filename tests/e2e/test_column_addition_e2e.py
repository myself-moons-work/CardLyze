import csv
import json
import io
import os
import socket
import sys
import threading
import time
from typing import Dict, List
import openpyxl
import pytest
import uvicorn
import xlsxwriter
import httpx

from playwright.sync_api import sync_playwright, Page, Browser, Error as PlaywrightError

from app.cards import get_card_config
from app.main import app
from app.store import session_store


CHROME_PATH = os.environ.get(
    "CHROME_PATH",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
)


def find_free_port() -> int:
    """Find an available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def app_server():
    """Start the FastAPI ASGI application on a free port in a background thread."""
    port = find_free_port()
    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server to come up
    base_url = f"http://127.0.0.1:{port}"
    start_time = time.time()
    up = False
    while time.time() - start_time < 10:
        try:
            with httpx.Client() as client:
                res = client.get(f"{base_url}/api/health", timeout=1.0)
                if res.status_code == 200:
                    up = True
                    break
        except Exception:
            time.sleep(0.1)

    if not up:
        server.should_exit = True
        raise RuntimeError("Failed to start FastAPI test server within timeout")

    yield base_url

    server.should_exit = True
    thread.join(timeout=3)


@pytest.fixture(scope="module")
def browser_instance():
    """Launch headless Chromium/Chrome instance for E2E tests."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME_PATH if os.path.exists(CHROME_PATH) else None,
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
        )
        yield browser
        browser.close()


def make_synthetic_raw_xlsx(num_cols: int, num_rows: int = 55) -> bytes:
    """Generate an in-memory synthetic Excel workbook without headers."""
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
        for c in range(num_cols):
            if r == 0 and c == 0:
                val = "00000003"  # Leading zeros string
            elif r == 0 and c == 1:
                val = "=1+1"  # Formula injection attempt
            elif r == 0 and c == 2:
                val = "https://example.com/portal"  # URL string
            else:
                val = f"r{r}_c{c}"
            ws.write_string(r, c, val)
    wb.close()
    return buf.getvalue()


CARDS_CONFIG = [
    ("visa", 29),
    ("pinelabs", 68),
    ("vegapay", 61),
]

VIEWPORTS = [
    {"name": "desktop", "width": 1280, "height": 800},
    {"name": "mobile", "width": 390, "height": 844},
]


@pytest.mark.e2e
@pytest.mark.parametrize("card_key, expected_cols", CARDS_CONFIG)
@pytest.mark.parametrize("viewport", VIEWPORTS)
def test_column_addition_e2e_workflow(
    app_server: str,
    browser_instance: Browser,
    card_key: str,
    expected_cols: int,
    viewport: dict,
):
    """End-to-end browser test for Column Addition across cards and viewports.

    Verifies:
    1. Zero console errors, zero uncaught page errors, zero CSP violations.
    2. Header count matches expected standardized columns.
    3. Sticky header row and sticky first column stay fixed while table scrolls.
    4. Document root scrollWidth <= innerWidth (zero horizontal page overflow).
    5. Pagination, rows-per-page selector, side drawer, column picker, density toggle.
    6. Excel download integrity (xlsx structure, row/col count, formula and leading zero preservation).
    7. Zero external network requests.
    """
    session_store.clear_all()
    context = browser_instance.new_context(
        viewport={"width": viewport["width"], "height": viewport["height"]},
        accept_downloads=True,
    )
    page = context.new_page()

    console_errors: List[str] = []
    page_errors: List[str] = []
    network_requests: List[str] = []

    # Monitor console messages (filter out benign favicon 404s if any)
    page.on(
        "console",
        lambda msg: console_errors.append(f"[{msg.type}] {msg.text}")
        if msg.type in ("error",) and "favicon" not in msg.text.lower() and "404" not in msg.text
        else None,
    )
    page.on("pageerror", lambda err: page_errors.append(str(err)))
    page.on("request", lambda req: network_requests.append(req.url))

    # Navigate to column addition page
    page.goto(f"{app_server}/column-addition.html")
    page.wait_for_load_state("domcontentloaded")

    # Install listener for SecurityPolicyViolation events
    page.evaluate(
        """() => {
        window.__cspViolations = [];
        document.addEventListener('securitypolicyviolation', (e) => {
            window.__cspViolations.push({
                blockedURI: e.blockedURI,
                violatedDirective: e.violatedDirective,
                originalPolicy: e.originalPolicy
            });
        });
    }"""
    )

    # 1. Select card
    card_btn = page.locator(f'.card-option[data-card="{card_key}"]')
    card_btn.click()
    assert "selected" in card_btn.get_attribute("class")

    # 2. Upload synthetic xlsx file in-memory
    synthetic_bytes = make_synthetic_raw_xlsx(num_cols=expected_cols, num_rows=55)
    file_payload = {
        "name": f"{card_key}_synthetic.xlsx",
        "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "buffer": synthetic_bytes,
    }
    page.set_input_files("#file-input", file_payload)

    # Click Process
    page.locator("#btn-process").click()

    # Wait for the preview table container to have table rows
    page.wait_for_selector("#preview-table-container .dt-table tbody tr", timeout=10000)

    # Assert success banner is visible
    success_banner = page.locator("#banner-success")
    assert not ("hidden" in (success_banner.get_attribute("class") or ""))

    # 3. Assert header count matches expected columns
    headers = page.locator("#preview-table-container .dt-table thead th")
    assert headers.count() == expected_cols

    # 4. Verify sticky header and sticky first column styling
    th_position = headers.first.evaluate("el => window.getComputedStyle(el).position")
    assert th_position == "sticky"

    first_col_cell = page.locator("#preview-table-container .dt-table tbody td.dt-td-sticky-first").first
    td_position = first_col_cell.evaluate("el => window.getComputedStyle(el).position")
    assert td_position == "sticky"

    # Scroll the table container horizontally and vertically
    scroll_box = page.locator("#preview-table-container .dt-scroll-container")
    scroll_box.evaluate("el => { el.scrollTop = 50; el.scrollLeft = 50; }")

    # 5. Assert document horizontal scroll width <= innerWidth (no page-level horizontal overflow)
    is_contained = page.evaluate(
        "() => document.documentElement.scrollWidth <= window.innerWidth"
    )
    assert is_contained, (
        f"Page overflowed horizontally on {viewport['name']} viewport! "
        f"scrollWidth={page.evaluate('() => document.documentElement.scrollWidth')} > "
        f"innerWidth={page.evaluate('() => window.innerWidth')}"
    )

    # 6. Pagination test: navigate to next page
    next_btn = page.locator('.dt-btn-nav[title="Next page"]')
    next_btn.click()
    page.wait_for_function(
        "() => document.querySelector('#preview-table-container .dt-page-info')?.textContent.includes('26 to 50')"
    )
    info_text = page.locator(".dt-page-info").text_content()
    assert "Showing 26 to 50 of 55" in info_text

    # Change rows per page to 50
    page.locator(".dt-page-size-select").select_option("50")
    page.wait_for_function(
        "() => document.querySelector('#preview-table-container .dt-page-info')?.textContent.includes('1 to 50')"
    )
    info_text_50 = page.locator(".dt-page-info").text_content()
    assert "Showing 1 to 50 of 55" in info_text_50

    # 7. Row detail side drawer
    first_row = page.locator("#preview-table-container .dt-table tbody tr").first
    first_row.click()
    drawer = page.locator(".dt-drawer")
    assert "open" in (drawer.get_attribute("class") or "")
    assert page.locator(".dt-drawer-title").is_visible()

    # Close drawer
    page.locator('.dt-btn-close[title="Close details (Esc)"]').click()
    assert "open" not in (drawer.get_attribute("class") or "")

    # 8. Column picker test
    picker_btn = page.locator(".dt-btn-col-picker")
    picker_btn.click()
    picker_menu = page.locator(".dt-col-picker-menu")
    assert "hidden" not in (picker_menu.get_attribute("class") or "")

    # Hide the second column by unchecking it
    second_col_checkbox = page.locator('.dt-picker-item input[type="checkbox"]').nth(1)
    second_col_checkbox.uncheck()
    page.wait_for_timeout(100)
    visible_headers = page.locator("#preview-table-container .dt-table thead th")
    assert visible_headers.count() == expected_cols - 1

    # Close picker menu
    picker_btn.click()

    # 9. Density toggle test
    table_el = page.locator("#preview-table-container .dt-table")
    assert "dt-compact" not in (table_el.get_attribute("class") or "")
    page.locator(".dt-btn-density").click()
    assert "dt-compact" in (table_el.get_attribute("class") or "")
    page.locator(".dt-btn-density").click()
    assert "dt-compact" not in (table_el.get_attribute("class") or "")

    # 10a. Download CSV (Fast Path) test
    assert page.locator("#csv-export-note").is_visible()
    with page.expect_download() as csv_download_info:
        page.locator("#btn-download-csv").click()
    csv_download = csv_download_info.value
    csv_tmp = csv_download.path()
    assert csv_tmp is not None
    with open(csv_tmp, "rb") as f:
        downloaded_csv_bytes = f.read()

    # Verify BOM, row count, column count, and plain text
    assert downloaded_csv_bytes.startswith(b"\xef\xbb\xbf")
    csv_rows = list(csv.reader(io.StringIO(downloaded_csv_bytes.decode("utf-8-sig")), lineterminator="\r\n"))
    assert len(csv_rows) == 56  # 1 header + 55 data rows
    assert len(csv_rows[0]) == expected_cols
    assert csv_rows[1][0] == "00000003"
    assert csv_rows[1][1] == "=1+1"

    # 10b. Download Excel test
    assert not page.locator("#excel-large-note").is_visible()
    with page.expect_download() as download_info:
        page.locator("#btn-download-excel").click()
    download = download_info.value
    download_tmp = download.path()
    assert download_tmp is not None
    with open(download_tmp, "rb") as f:
        downloaded_bytes = f.read()

    # Inspect downloaded workbook
    wb = openpyxl.load_workbook(io.BytesIO(downloaded_bytes))
    sheet = wb.active
    assert sheet.max_row == 56  # 1 header row + 55 data rows
    assert sheet.max_column == expected_cols

    # Verify plain text preservation
    cell_val_0 = sheet.cell(2, 1).value
    assert str(cell_val_0) == "00000003"
    assert sheet.cell(2, 1).data_type == "s"

    cell_val_1 = sheet.cell(2, 2).value
    assert str(cell_val_1) == "=1+1"
    assert sheet.cell(2, 2).data_type == "s"

    # 11. Assert no external requests occurred
    for req_url in network_requests:
        assert req_url.startswith(app_server) or req_url.startswith("blob:") or req_url.startswith("data:"), (
            f"Forbidden external network request detected: {req_url}"
        )

    # 12. Assert zero console errors & zero CSP violations
    csp_violations = page.evaluate("() => window.__cspViolations || []")
    assert len(csp_violations) == 0, f"CSP violations detected: {csp_violations}"
    assert len(console_errors) == 0, f"Browser console errors detected: {console_errors}"
    assert len(page_errors) == 0, f"Uncaught page errors detected: {page_errors}"

    context.close()


@pytest.mark.e2e
def test_column_addition_errors_and_session_expiry(
    app_server: str,
    browser_instance: Browser,
):
    """Test column-count mismatch, already-has-headers error banners, and expired session message."""
    session_store.clear_all()
    context = browser_instance.new_context(
        viewport={"width": 1280, "height": 800},
        accept_downloads=True,
    )
    page = context.new_page()
    page.goto(f"{app_server}/column-addition.html")
    page.wait_for_load_state("domcontentloaded")

    # Select VISA (expects 29 columns)
    page.locator('.card-option[data-card="visa"]').click()

    # 1. Trigger wrong-column-count error: upload 10 columns
    bad_bytes = make_synthetic_raw_xlsx(num_cols=10, num_rows=10)
    page.set_input_files(
        "#file-input",
        {
            "name": "visa_bad_columns.xlsx",
            "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "buffer": bad_bytes,
        },
    )
    page.locator("#btn-process").click()

    page.wait_for_selector("#banner-error", state="visible")
    err_desc = page.locator("#banner-error-desc").text_content()
    assert "found 10 columns, expected 29" in err_desc

    # 2. Trigger already-has-headers error:
    # First row contains actual VISA headers
    visa_cfg = get_card_config("visa")
    header_row = visa_cfg.expected_columns
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    ws = wb.add_worksheet()
    for col_idx, h in enumerate(header_row):
        ws.write_string(0, col_idx, h)
    for col_idx in range(len(header_row)):
        ws.write_string(1, col_idx, "dummy_data")
    wb.close()
    headers_already_bytes = buf.getvalue()

    # Click Try Again to reset
    page.locator("#btn-error-retry").click()
    page.set_input_files(
        "#file-input",
        {
            "name": "visa_already_headers.xlsx",
            "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "buffer": headers_already_bytes,
        },
    )
    page.locator("#btn-process").click()

    page.wait_for_selector("#banner-error", state="visible")
    err_desc2 = page.locator("#banner-error-desc").text_content()
    assert "already contains" in err_desc2.lower() and "headers" in err_desc2.lower()

    # 3. Successful upload then simulate session expiration
    page.locator("#btn-error-retry").click()
    good_bytes = make_synthetic_raw_xlsx(num_cols=29, num_rows=15)
    page.set_input_files(
        "#file-input",
        {
            "name": "visa_good.xlsx",
            "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "buffer": good_bytes,
        },
    )
    page.locator("#btn-process").click()
    page.wait_for_selector("#preview-table-container .dt-table tbody tr")

    # Wipe session behind the page's back in the backend store
    session_store.clear_all()

    # Now attempt to download
    page.locator("#btn-download-csv").click()

    # Verify session expired message is displayed in error banner
    page.wait_for_selector("#banner-error", state="visible")
    expired_desc = page.locator("#banner-error-desc").text_content()
    assert "session has expired" in expired_desc.lower()

    context.close()


@pytest.mark.e2e
def test_xss_prevention_in_dom(
    app_server: str,
    browser_instance: Browser,
):
    """Verify that malicious XSS strings injected in cells and headers do not execute and render as literal text."""
    session_store.clear_all()
    context = browser_instance.new_context(
        viewport={"width": 1280, "height": 800},
    )
    page = context.new_page()

    # Collect any dialogs (alerts, prompts, confirms) - should NEVER be triggered!
    dialog_messages: List[str] = []
    page.on("dialog", lambda d: dialog_messages.append(d.message))

    page.goto(f"{app_server}/column-addition.html")
    page.wait_for_load_state("domcontentloaded")

    # Install listener for SecurityPolicyViolation events
    page.evaluate(
        """() => {
        window.__cspViolations = [];
        document.addEventListener('securitypolicyviolation', (e) => {
            window.__cspViolations.push(e.violatedDirective);
        });
    }"""
    )

    page.locator('.card-option[data-card="visa"]').click()

    # Build synthetic file with XSS payloads
    xss_payloads = [
        "<img src=x onerror=alert(1)>",
        "<script>alert('xss')</script>",
        "';alert(String.fromCharCode(88,83,83))//",
        "<svg/onload=alert('svg')>",
    ]
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True, "strings_to_formulas": False})
    ws = wb.add_worksheet()
    # Row 1 with XSS payloads
    for col_idx in range(29):
        val = xss_payloads[col_idx % len(xss_payloads)]
        ws.write_string(0, col_idx, val)
    wb.close()

    page.set_input_files(
        "#file-input",
        {
            "name": "xss_injection.xlsx",
            "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "buffer": buf.getvalue(),
        },
    )
    page.locator("#btn-process").click()

    page.wait_for_selector("#preview-table-container .dt-table tbody tr")

    # 1. Assert cell content renders literally
    first_cell = page.locator("#preview-table-container .dt-table tbody tr td.dt-td-sticky-first").first
    assert first_cell.text_content() == "<img src=x onerror=alert(1)>"

    second_cell = page.locator("#preview-table-container .dt-table tbody tr td.dt-td").nth(1)
    assert second_cell.text_content() == "<script>alert('xss')</script>"

    # 2. Check tooltip
    assert first_cell.get_attribute("title") == "<img src=x onerror=alert(1)>"

    # 3. Open drawer and verify drawer value is rendered as plain text
    page.locator("#preview-table-container .dt-table tbody tr").first.click()
    page.wait_for_selector(".dt-drawer.open")

    drawer_values = page.locator(".dt-drawer-value")
    assert drawer_values.first.text_content() == "<img src=x onerror=alert(1)>"
    assert drawer_values.nth(1).text_content() == "<script>alert('xss')</script>"

    # Close drawer before clicking other elements
    page.locator('.dt-btn-close[title="Close details (Esc)"]').click()
    page.wait_for_function("() => !document.querySelector('.dt-drawer')?.classList.contains('open')")

    # 4. Check column picker
    page.locator(".dt-btn-col-picker").click()
    page.wait_for_selector(".dt-col-picker-menu")

    # 5. Assert no alerts / prompts / confirms popped
    assert len(dialog_messages) == 0, f"XSS alert dialog popped: {dialog_messages}"

    # 6. Assert no CSP violations
    csp_violations = page.evaluate("() => window.__cspViolations || []")
    assert len(csp_violations) == 0, f"CSP violation fired: {csp_violations}"

    context.close()


@pytest.mark.e2e
def test_large_file_excel_warning_in_ui(
    app_server: str,
    browser_instance: Browser,
):
    """Test that files with > 60,000 rows display the Excel warning notice in the UI."""
    session_store.clear_all()
    context = browser_instance.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()

    # Intercept upload response to return rows: 65,000
    def handle_upload(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({
                "ok": True,
                "rows": 65000,
                "columns": ["col1", "col2"],
                "column_count": 2,
                "card_key": "visa",
                "is_large_file": True,
                "preview": {
                    "page": 1,
                    "page_size": 25,
                    "total_rows": 65000,
                    "total_pages": 2600,
                    "columns": ["col1", "col2"],
                    "rows": [{"col1": "a", "col2": "b"}],
                },
            }),
        )

    page.route("**/api/column-addition/*/upload", handle_upload)
    page.goto(f"{app_server}/column-addition.html")
    page.wait_for_load_state("domcontentloaded")

    # Select VISA and upload small file
    page.locator('.card-option[data-card="visa"]').click()
    raw_bytes = make_synthetic_raw_xlsx(num_cols=29, num_rows=5)
    page.set_input_files(
        "#file-input",
        {
            "name": "visa_sample.xlsx",
            "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "buffer": raw_bytes,
        },
    )
    page.locator("#btn-process").click()
    page.wait_for_selector("#banner-success", state="visible")

    # Verify #excel-large-note is visible
    large_note = page.locator("#excel-large-note")
    assert large_note.is_visible()
    assert "Excel export can take several minutes" in large_note.text_content()

    context.close()
