# CardLyze

CardLyze is a secure, privacy-first internal web tool for processing, standardizing, and analyzing credit and debit card transaction data from major card providers (VISA, PineLabs, and Vegapay).

## Key Features

1. **Column Addition**: Upload raw header-less transaction files, automatically map standard schema headers, preview paginated rows in-memory, and download verified `.xlsx` files.
2. **Analysis**: Upload standardized transaction files, filter across multiple dimensions (including faceted Country and MCC filters), perform full-text search, analyze column statistics, and export filtered slices.
3. **Strict Privacy Architecture**:
   - Zero disk persistence: All processing happens purely in RAM (`io.BytesIO`, Pandas DataFrames).
   - Raw streaming uploads: Avoids multipart temporary disk spooling.
   - Ephemeral in-memory sessions: Datasets are tied to short-lived sessions and wiped upon exit.
   - Comprehensive security headers applied across all responses.

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

To run the application locally:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

> **Note on single worker**: CardLyze uses an in-memory session store to guarantee zero disk persistence. A single worker ensures all requests for a session hit the same memory space.

## Running Tests

Run the test suite with pytest:

```bash
pytest
```

## Configuration

Settings can be customized in `app/config.py` or via environment variables:
- `HOST`: Default `127.0.0.1`
- `PORT`: Default `8000`
- `MAX_UPLOAD_SIZE_BYTES`: Default `52428800` (50 MB)
- `SESSION_TTL_SECONDS`: Default `1800` (30 minutes)
- `MAX_CONCURRENT_SESSIONS`: Default `10`
