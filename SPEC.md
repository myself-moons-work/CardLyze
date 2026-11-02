# CardLyze Specification & Architecture Guide

## 1. Product Overview
**CardLyze** is a secure, lightweight internal web application developed for analyzing and processing credit and debit card transaction datasets for an organization. It bridges exploratory data workflows and operational reporting with absolute privacy guarantees.

The application provides two core workflows sharing a common top navigation bar:
1. **Column Addition**: Users select a card type (VISA, PineLabs, or Vegapay), upload a raw header-less Excel file, preview the data with the correct column names mapped, and download the standardized file as an `.xlsx` workbook.
2. **Analysis**: Users select a card type, upload a formatted Excel file with headers (under 50 MB), and perform in-depth analysis through multi-column filtering, global search, column selection, faceted unique-value exploration, column statistics, and filtered Excel exports.

---

## 2. Technology Stack & Operational Constraints
- **Backend**:
  - Python 3.11+
  - **FastAPI** & **Starlette**: Asynchronous web framework and routing.
  - **Uvicorn**: ASGI web server running with a **single worker process**.
    > *Why single worker?* All session data and datasets reside strictly in-memory. Running a single worker guarantees that all incoming requests route to the same memory space without requiring external state stores (like Redis or databases) which would violate privacy constraints.
  - **Pandas**: In-memory data manipulation, filtering, and analysis.
  - **openpyxl** & **python-calamine**: In-memory Excel parsing and serialization. `python-calamine` is used where available for accelerated parsing with openpyxl fallback.
  - **Pytest** & **HTTPX**: Comprehensive automated testing, including test clients and simulated streaming uploads.
- **Frontend**:
  - Plain HTML5, CSS3, and modern vanilla JavaScript (ES6+).
  - Served directly via FastAPI `StaticFiles`.
  - **Zero build steps, zero external CDNs, zero third-party JavaScript libraries, and zero external web fonts or telemetry**.
- **Network & Binding**:
  - Binds to `127.0.0.1` by default (configurable via environment variables / configuration file).
  - Designed to operate locally or behind an authenticated enterprise HTTPS reverse proxy.

---

## 3. Privacy & Security Rules (Strict & Non-Negotiable)

Card transaction datasets contain sensitive financial and personal details. The following rules are architectural invariants:

### 3.1 Zero Disk Persistence
- **No data is ever written to disk**: No upload temp files, spool files, cached frames, intermediate files, or disk exports.
- All file parsing, processing, and transformations must occur entirely in RAM using `io.BytesIO` streams and Pandas DataFrames.
- Codebase audits continuously verify that no calls to `tempfile`, `open(..., "w")`, `to_excel()` with file paths, or persistent disk stores (`sqlite3`, `shelve`, `pickle`) touch user data.

### 3.2 Raw Streaming Uploads (No Multipart Spooling)
- Standard HTTP multipart form parsers (including Starlette's `UploadFile` and `python-multipart`) spool files larger than 1 MB directly to disk via `tempfile.SpooledTemporaryFile`.
- **Multipart uploads are strictly forbidden for data files.**
- Uploads must be submitted as raw binary request bodies:
  - Binary payload streamed directly via `request.stream()`.
  - The original filename is communicated via the custom header `X-Filename`.
  - The server reads the stream chunk-by-chunk into an `io.BytesIO` buffer.
  - If incoming bytes exceed 50 MB (`MAX_UPLOAD_SIZE_BYTES`), the connection is immediately aborted with HTTP 413 (Payload Too Large) without buffering further.

### 3.3 Ephemeral In-Memory Session Store
- Datasets are stored exclusively in an in-memory `SessionStore` keyed by a high-entropy cryptographically secure token (`secrets.token_urlsafe(32)`).
- **Client Storage Constraint**: The client browser retains the session token solely in a JavaScript runtime memory variable (closure state). Tokens must **never** be persisted in `localStorage`, `sessionStorage`, cookies, or `IndexedDB`.
- Tokens are transmitted via the `X-Session-Id` HTTP header.
- **Session Limits**:
  - **Idle TTL**: 30 minutes of inactivity (configurable).
  - **Concurrency Cap**: Maximum 10 concurrent active sessions (configurable). Attempts to create an 11th session return HTTP 503 (Service Unavailable).
  - **Wipe & Deletion**: Explicit `DELETE /api/session` clears all references to DataFrames, enabling immediate Python garbage collection.
  - **Background Sweeper**: A periodic asynchronous task purges expired sessions.
  - **Deterministic Clock**: The session store accepts an injectable time function (`time_func`) for testing expiration without sleeping.

### 3.4 Zero Data Leakage in Logs and URLs
- Error messages and logs must **never echo cell values**, customer names, account numbers, or card numbers.
- Query strings and URLs must never contain transaction data.
- In parse warnings or data quality reports, only abstract structural shapes (replacing digits with `9` and letters with `A`, e.g., `99-99-9999`) and row counts may be reported.

### 3.5 Mandatory HTTP Security Headers
Every HTTP response (both dynamic API endpoints and static assets) must carry:
```http
Cache-Control: no-store
Referrer-Policy: no-referrer
X-Content-Type-Options: nosniff
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:;
```

---

## 4. Card Schema Definitions

The application supports three card transaction schemas defined in `app/cards.py`:

| Card Source | Expected Columns | Key Identifiers / Text Columns | Date Columns & Explicit Formats | MCC Column | Derived Country Code Rule |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **VISA** | 29 | `spcati`, card/account numbers | `spbusd`: `%Y-%m-%d`<br>`spdate`: `%d%m%Y` (zfill to 8 digits) | `spmcat` | Last whitespace-delimited token of `spldes` (e.g., `"CHOPSTIX BEACONSFIELD GB"` $\rightarrow$ `"GB"`) |
| **PineLabs** | 68 | IDs, codes with leading zeros | `Value Date`: `%d/%m/%Y %H:%M:%S`, `%d/%m/%Y`<br>`Transaction Date`: `%d/%m/%Y %H:%M:%S`, `%d/%m/%Y` | `mcc` | Last 2-letter uppercase token of `Merchant Name & Location`, else `"Unknown"` |
| **Vegapay** | 61 | `Transaction Code`, account IDs | `Business Date`: `%Y-%m-%d`, `%Y-%m-%d %H:%M:%S`<br>`DOB`: `%d-%m-%Y`, `%d-%m-%Y %H:%M:%S`<br>`Mastercard Date`: `%d-%m-%Y`, `%d-%m-%Y %H:%M:%S`<br>`Transaction Date`: `%d-%m-%Y`, `%d-%m-%Y %H:%M:%S`<br>`Settlement Date`: `%Y-%m-%d`, `%Y-%m-%d %H:%M:%S` | `MCC` | Sourced directly from `Merchant Country`. Sensitive cols (`Passport Number`, `DOB`) hidden by default |

### Date Parsing Rules
- **Never guess formats**: Pandas automatic date parsing is strictly disabled. Formats are tried strictly in configured priority order against unparsed rows.
- Known null tokens (e.g., `"-"`, `""`, whitespace, `"NaT"`) are treated as blanks without triggering parse error warnings.
- Parse warnings report the count of unparseable rows and the top 3 structural shapes (e.g., `9999-99-99`).

---

## 5. API Endpoints Overview

### Phase 1 Core Endpoints
- `GET /api/health`: Healthcheck endpoint returning `{"status": "ok"}`.
- `POST /api/session`: Initiates a new session; returns `{"session_id": "<token>"}` with HTTP 201. Returns HTTP 503 if $\ge 10$ active sessions exist.
- `DELETE /api/session`: Explicitly wipes session datasets and invalidates the session ID.

### Phase 2 & 3: Column Addition Endpoints
- `POST /api/column-addition/{card_key}/upload`: Streams raw Excel bytes, validates shape against expected schema, stores DataFrame in session store, and returns summary and first preview page.
- `GET /api/column-addition/preview`: Server-side paginated preview (`page`, `page_size`).
- `GET /api/column-addition/export`: Generates an in-memory `.xlsx` stream with headers applied.
- `DELETE /api/column-addition`: Wipes the column addition dataset for the session.

### Phase 4 & 5: Analysis Endpoints
- `POST /api/analysis/{card_key}/upload`: Streams raw Excel file with headers, applies explicit typing, derives country code, and returns schema metadata and parse warnings.
- `POST /api/analysis/query`: Filters, searches, sorts, and paginates the dataset. Caches filtered indices in session for rapid pagination.
- `POST /api/analysis/unique`: Faceted unique value listing for a specific column, omitting the active filter on that column.
- `GET /api/analysis/stats`: Computes column-level metrics (min, max, mean, sum, unique counts).
- `POST /api/analysis/export`: In-memory `.xlsx` stream of the filtered dataset with currently visible columns.
- `DELETE /api/analysis`: Wipes the analysis dataset for the session.

---

## 6. Frontend Architecture
- **Responsive Layout**: Designed for desktop and tablet displays, with graceful collapse to single-column drawers on mobile viewports.
- **Reusable DataTable Component (`app/static/js/common.js`)**:
  - Independent scrolling container (max height $\approx 60\text{vh}$).
  - Sticky header row and sticky first column.
  - Server-side pagination controls and page-size selector (25, 50, 100).
  - Truncated text with full tooltip view.
  - Row detail slide-over panel for wide schemas (e.g., PineLabs with 68 columns).
  - Multi-select column visibility dropdown with search and quick actions ("Key columns", "Select All", "Clear").
  - Table density toggle (compact vs. comfortable).
  - Right-aligned numbers and left-aligned text; blanks represented as subtle dashes (`—`).
- **Session Lifecycle in UI**:
  - Obtains session ID on page load.
  - Binds `beforeunload` / `unload` events with `navigator.sendBeacon` or `fetch` with `keepalive: true` to trigger `DELETE /api/session`.


---

## 7. Implementation Directives & Architecture Addenda

The following engineering directives apply across all subsequent phases:
1. **Strict Content-Security-Policy Compliance**:
   - `Content-Security-Policy: default-src 'self'` strictly blocks inline scripts (`<script>...</script>`), inline event listeners (`onclick="..."`), inline `<style>` tags, and inline HTML `style="..."` attributes.
   - All frontend behaviors, stylings, and layout rules must strictly reside in external JavaScript files (`app/static/js/*.js`) and external stylesheets (`app/static/css/*.css`).
   - Excel exports and streaming downloads must be tested to ensure compliance under this policy without requiring inline blobs or unsafe eval/styles.
2. **Lazy Client Session Initialization**:
   - Sessions must be created lazily on the first file upload rather than proactively on page load.
   - This prevents idle/phantom sessions from consuming slots in the 10-session concurrent limit when users merely browse or reload the landing page.
3. **Session Concurrency Cap Calibration**:
   - The default limit of 10 concurrent active sessions will be scientifically measured and calibrated based on actual memory consumption during the Phase 6 performance testing suite (using ~50 MB benchmark files).
4. **Synthetic Test Data Exclusivity**:
   - Pytest suites must use purely synthetic test data generated in-memory.
   - Real transaction files must never be required for automated tests. Any test referencing an optional local real file must skip automatically when absent and be excluded from default test runs.
5. **Single Source of Truth for Card Configurations**:
   - `app/cards.py` is the sole source of truth for schema definitions, column lists, date parsing configurations, and type mappings.
   - Legacy scripts or notebooks must import directly from `app.cards`.
