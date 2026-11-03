Read SPEC.md first. Build Phase 3: the Column Addition feature end to end, plus the reusable preview table (DataTable) that the Analysis page will reuse. Branch feature/phase-3 from main. Use the EXISTING app/cards.py, app/services/headers.py, app/services/concurrency.py and the session store. Do not re-implement them. Never run anything on real data files: use synthetic data in tests, and write any real-data script under scratch/ for me to run, printing counts and shapes only.

BACKEND (app/routers/column_addition.py), all data in the session store only:
- POST /api/column-addition/{card_key}/upload: raw body (read_limited_body), headers X-Session-Id and X-Filename. Accept .xlsx only. Run parsing in the thread pool, limited by the existing parse semaphore, with a clear "server busy, try again" message when it is full. Call add_headers; on success store the DataFrame in the session and return rows, column count, a "large file" flag (over 30 MB) and the first preview page. On failure return 422 with the readable message (found vs expected columns, or already has headers) and store nothing. Log only duration, file size and card key, never data.
- GET /api/column-addition/preview?page=&page_size= (25, 50 or 100; server-side pagination; columns in card order).
- GET /api/column-addition/export: builds the xlsx in memory in the thread pool and streams it as {card}_with_headers_{YYYYMMDD}.xlsx. The exported values must equal the input values exactly (no padding, no type conversion).
- DELETE /api/column-addition: wipe that dataset.

EXPORT ENGINE (important):
- Writing 150k rows x 29 columns with openpyxl is slow. Use xlsxwriter in normal in-memory mode with BytesIO. Do NOT use constant_memory (it writes temp files to disk, which breaks the no-disk rule). Add xlsxwriter to requirements.
- Both openpyxl and xlsxwriter's write() interpret strings starting with "=" as formulas, and xlsxwriter turns URL-looking strings into hyperlinks. Pass options so strings are written as plain text: strings_to_formulas False, strings_to_urls False, strings_to_numbers False. Add tests that "=1+1", "+cmd", "@x" and "http://example.com" survive as text, and that "00000003" stays text.
- Write scratch/export_bench.py for me to run: it loads one real file with add_headers and prints export time and peak process RSS (psutil background sampler) for xlsxwriter and for openpyxl, so we can confirm the choice.

FRONTEND (static/column-addition.html, js/common.js, js/column_addition.js, css/app.css). CSP is default-src 'self': external JS and CSS only, no inline scripts, no inline event handlers, no style="" attributes.
- Three steps on one page: (1) choose card as three large selectable options showing the expected column count; (2) upload via drop zone or button (.xlsx only, client-side 50 MB check, file name and size shown); (3) result: success or error banner, then the preview with "Download Excel" and "Clear data" buttons.
- Sessions are created lazily: on first upload call POST /api/session, keep the token in a JS variable only, send X-Session-Id. Skip the unload DELETE when no session exists.
- While parsing show an indeterminate loading state with the file name and an elapsed-seconds timer; for files over 30 MB add the note "Large file, this can take about a minute". Same for export ("Preparing Excel file...").
- If the session has expired (401), explain it and offer to upload again. Disable the buttons during requests.
- DownloAD: fetch the export with the session header, create a blob URL, trigger download via an anchor, then revoke the URL. Verify this works under the CSP.
- DataTable component in common.js (reused by the Analysis page): DataTable(container, options) where options include a list of hidden column names (internal columns such as _raw_* must never be shown or selectable). Requirements:
  * Scrolls inside its own box (max-height about 60vh); the page never scrolls sideways.
  * Sticky header row and sticky first column.
  * Server-side pagination with a rows-per-page selector, first/prev/next/last, and "showing X to Y of N".
  * Long cells truncated with an ellipsis and the full text in a tooltip; column widths capped.
  * Row detail side panel: click a row to see all its fields as a vertical name/value list with a copy button (this avoids horizontal scrolling on wide rows).
  * Column picker dropdown: checkbox list with search; shortcuts "Select all", "Clear" and "Key columns".
  * Compact/comfortable density toggle.
  * Numbers right-aligned, text left-aligned, empty values as a faint dash, whitespace collapsed for display.
- Responsive from tablet to desktop, single column on phones. Keyboard accessible, visible focus, readable contrast, 14px+ text.
- On page unload send a keepalive DELETE if a session exists. Store nothing in the browser (no localStorage, cookies or IndexedDB).

TESTS (pytest with TestClient, synthetic files built in memory):
- Upload succeeds for each card; preview pagination boundaries (first, last, beyond last page); page_size validation.
- Mismatch returns 422 and nothing is stored; already-has-headers returns 422.
- Export is a valid xlsx with correct headers and values; values equal input exactly; formula, URL and leading-zero text cases as above.
- Session isolation (session B cannot read session A); DELETE wipes; missing or invalid session returns 401.
- Oversize body returns 413; non-.xlsx rejected.
- A slow upload does not block /api/health; the parse semaphore limit returns the busy message.
- The no-disk test still passes with a 5 MB upload AND an export through these routes.
- A test that the static pages contain no inline script, no inline style attributes and no on*= handlers.

Run pytest and show the output. Then verify the page in a real browser (use the browser tool if you have one) at desktop and about 390 px width, with a synthetic file for each card, and report exactly what you checked, including that the download works under the CSP. Commit (confirm with git show --stat HEAD that no scratch or data files are included) and push.