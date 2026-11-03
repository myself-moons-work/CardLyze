# CardLyze

CardLyze is a secure, privacy-first internal web tool for processing, standardizing, and analyzing credit and debit card transaction data from major card providers (VISA, PineLabs, and Vegapay).

## Key Features

1. **Column Addition**: Upload raw header-less transaction workbooks, automatically map standard schema headers, preview paginated rows in-memory, and export verified datasets via **Fast Streaming CSV** or **Excel (.xlsx)**.
2. **Analysis**: Upload standardized transaction files, filter across multiple dimensions (including faceted Country and MCC filters), perform full-text search, analyze column statistics, and export filtered slices.
3. **Strict Privacy Architecture**:
   - Zero disk persistence: All processing happens purely in RAM (`io.BytesIO`, Pandas DataFrames, in-memory chunk streams).
   - Raw streaming uploads: Avoids multipart temporary disk spooling.
   - Ephemeral in-memory sessions: Datasets are tied to short-lived sessions and wiped upon exit.
   - Strict Content Security Policy (CSP): `default-src 'self'` with zero inline scripts or unsafe eval.

## Installation & Setup

Requirements: Python 3.11+
Required Dependencies: `python-calamine` (primary in-memory Excel engine for high performance and minimal memory usage; `openpyxl` is retained as an explicit fallback).

```bash
# Clone the repository
git clone <repo-url>
cd CardLyze

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Running the Application

CardLyze is designed as a single-user local application bound to the loopback interface (`127.0.0.1`):

```bash
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

> **Note on single worker**: CardLyze uses an in-memory session store to guarantee zero disk persistence. A single worker ensures all requests for a session hit the same memory space.

## Running Tests

Run the test suite with pytest:

```bash
# Run unit and integration tests (synthetic in-memory data only)
.\.venv\Scripts\python.exe -m pytest -v

# Run Playwright end-to-end browser tests
.\.venv\Scripts\python.exe -m pytest -v -m e2e
```

## Configuration & Local Limits

CardLyze defaults are tuned for local single-user execution on laptops. Settings can be overridden via environment variables:

| Variable | Default | Description |
|---|---|---|
| `CARDLYZE_HOST` | `127.0.0.1` | Host to bind server to. |
| `CARDLYZE_PORT` | `8000` | Port to bind server to. |
| `MAX_SESSIONS` | `2` | Maximum concurrent active in-memory sessions. |
| `MAX_PARALLEL_PARSES` | `1` | Maximum simultaneous file parse tasks. |
| `MAX_PARALLEL_EXPORTS` | `1` | Maximum simultaneous Excel export tasks. |
| `ALLOW_NON_LOOPBACK` | `0` | If set to `1`, permits binding to external/non-loopback interfaces (prints security warning). By default, refuses to start on non-loopback hosts. |
| `CARDLYZE_MAX_UPLOAD_SIZE_BYTES` | `52428800` | Maximum file upload size in bytes (50 MB). |
| `CARDLYZE_SESSION_TTL_SECONDS` | `1800` | Session inactivity timeout in seconds (30 minutes). |

## Hardware Guidance

The following guidelines provide **ESTIMATES** (not guaranteed benchmarks) for running CardLyze locally on a colleague's laptop with **6 GB RAM** and a **2015-era dual-core CPU**:

### Memory Baseline & Capacity (Estimates)
- **Host Baseline**: Modern Windows 10/11 with typical background processes requires ~2.5 to 3.5 GB RAM.
- **Available RAM for CardLyze**: Approximately ~2.5 to 3.5 GB free.
- **Estimated Dataset Memory Usage**:
  - **Vegapay** (~1,200 rows x 61 columns): ~50–80 MB peak RAM.
  - **PineLabs** (~48,000 rows x 68 columns): ~150–250 MB peak RAM.
  - **VISA** (~154,000 rows x 29 columns, ~4.5M cells): ~400–600 MB peak RAM during parse or Excel generation.

### Export Format Recommendations
- **Download CSV (Fast, Recommended for Large Files)**:
  - **Time To First Byte**: ~0.5 to 2 seconds.
  - **Total Generation Time**: ~2 to 5 seconds for 150k rows.
  - **Memory Impact**: Negligible (~25 MB delta) because rows stream in 20,000-row chunks directly to the browser.
  - **Excel Import Note**: When opening large CSVs in Excel, double-clicking can drop leading zeros (e.g. `00000003` -> `3`) or parse text starting with `=` as a formula. Use Excel's **Data > From Text/CSV** wizard and explicitly set columns to **Text**, or load in Python using `pandas.read_csv(..., dtype=str)`.
- **Download Excel (.xlsx)**:
  - Generates a full native `.xlsx` workbook using `xlsxwriter`.
  - On a 2015-era dual-core processor, serializing and compressing 4.5 million XML cells can take **2 to 4 minutes** of sustained CPU work.
  - For files exceeding 60,000 rows, CardLyze automatically displays a warning notice on the Excel export button.

> **Operational Tip**: Before uploading large VISA-size transaction workbooks (~150,000+ rows) on 6 GB machines, please close heavy applications (such as browsers with many tabs, video calls, or IDEs) to prevent memory paging or system slowdown.
