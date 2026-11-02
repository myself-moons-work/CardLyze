Build a simple internal web tool called "CardLyze". This phase sets up the project, the spec and the privacy foundation only. No card logic yet.

PRODUCT
Two pages sharing one nav bar:
1. Column Addition: the user picks a card source (VISA, PineLabs, Vegapay), uploads a header-less Excel file, previews it with the correct column names added, then downloads it as Excel.
2. Analysis: the user picks a card source, uploads the Excel file (with headers, under 50 MB), then explores it with filters, search, a column picker and unique-value views.
Reference material is in /reference (Card_Data.ipynb has the existing logic, Transaction_Data_Dictionary.docx has the columns). Do not edit /reference.

STACK (keep it simple)
Python 3.11+, FastAPI, uvicorn, pandas, openpyxl, python-calamine (optional faster Excel reader, fall back to openpyxl), pytest, httpx. Frontend is plain HTML, CSS and vanilla JS served by FastAPI StaticFiles. No frameworks, no build step, no CDN, no external fonts or scripts.

PRIVACY RULES (non-negotiable; this data is sensitive and belongs to an organization)
- Never write user data to disk: no uploads, temp files, caches, logs or exports on disk. Process in memory (BytesIO / DataFrames) only.
- Do NOT use multipart form uploads (Starlette spools files over 1 MB to a temp file). Use raw-body uploads: the browser POSTs the File as the request body, the filename goes in an X-Filename header, and the server reads request.stream() into a BytesIO, aborting with HTTP 413 beyond 50 MB.
- Data lives only in a server-side in-memory SessionStore keyed by a random token (secrets.token_urlsafe(32)). The browser keeps the token in a JS variable only (not localStorage or cookies) and sends it in an X-Session-Id header.
- Sessions: idle TTL 30 min (configurable), max 10 concurrent sessions (configurable, reject with 503 beyond that), explicit delete endpoint, background sweeper, injectable clock for tests. Run with a single worker (document why).
- Never log cell values or file contents. Error messages must not echo cell values. Disable uvicorn access logs for /api paths or ensure no data appears in URLs (data is never in query strings).
- Response headers on everything: Cache-Control: no-store, Referrer-Policy: no-referrer, X-Content-Type-Options: nosniff, and Content-Security-Policy: default-src 'self'.
- Bind to 127.0.0.1 by default (configurable).
- .gitignore must exclude *.xlsx, *.xls, *.csv, data folders and notebook outputs.

DELIVERABLES
1. Folder structure:
   app/ main.py config.py security.py store.py uploads.py cards.py (empty stub for now) routers/ services/ static/{css,js}
   tests/ reference/ SPEC.md README.md requirements.txt .gitignore
2. SPEC.md: write this whole brief (product, stack, privacy rules, and the API/UI requirements I give in later phases as they come) so later phases can read it first.
3. security.py: headers middleware.
4. store.py: SessionStore as described, holding per-session dicts for the "coladd" and "analysis" datasets, with a wipe method that drops all references.
5. uploads.py: read_limited_body(request, max_bytes) -> bytes, streaming, 413 on overflow.
6. Endpoints: GET /api/health, POST /api/session (create), DELETE /api/session (wipe). A static landing page with the nav bar and placeholder links for the two pages.
7. pytest tests: TTL expiry via fake clock, session cap, delete wipes data, security headers present on API and static responses, oversize body returns 413, and a NO-DISK test (snapshot the system temp dir and the project dir before and after a 5 MB upload and assert nothing new was created; also monkeypatch tempfile.SpooledTemporaryFile and NamedTemporaryFile to raise).