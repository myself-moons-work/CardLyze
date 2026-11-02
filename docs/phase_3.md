Read SPEC.md first. Build the Column Addition feature end to end, including the reusable preview table that the Analysis page will reuse.

BACKEND (routers/column_addition.py), all data held only in the session store:
- POST /api/column-addition/{card_key}/upload: raw body, X-Filename and X-Session-Id headers. Accept .xlsx only. Validate with add_headers. On success store the DataFrame in the session and return rows, column count and the first preview page. On failure return a 422 with the readable message (found vs expected columns) and store nothing.
- GET /api/column-addition/preview?page=&page_size= (page_size 25/50/100; server-side pagination; JSON rows).
- GET /api/column-addition/export: streams the xlsx from memory (StreamingResponse over BytesIO) as {card}_with_headers_{YYYYMMDD}.xlsx.
- DELETE /api/column-addition: wipe that dataset.

FRONTEND (static/column-addition.html, js/common.js, js/column_addition.js, css/app.css)
- Three steps on one page: (1) choose card as three large selectable options showing the expected column count, (2) upload via a drop zone or file button (.xlsx only, client-side 50 MB check, loading indicator), (3) result: a success or error banner, then the preview and the buttons "Download Excel" and "Clear data".
- Build the preview as a REUSABLE component in common.js: DataTable(container, options). Requirements:
  * Scrolls inside its own box (max-height about 60vh); the page itself never scrolls sideways.
  * Sticky header row and sticky first column.
  * Server-side pagination with rows-per-page selector, first/prev/next/last, and "showing X to Y of N".
  * Long cells truncated with an ellipsis and full text in a tooltip; column widths capped.
  * "Row detail" side panel: click a row to see all its fields as a vertical name/value list (this avoids horizontal scrolling for wide rows like PineLabs with 68 columns) with a copy button.
  * Column picker dropdown (checkbox list with search, "Select all / Clear / Key columns" shortcuts) to choose which columns to display.
  * Compact/comfortable density toggle.
  * Numbers right-aligned, text left-aligned, empty values shown as a faint dash.
- Responsive: usable from tablet width up, and degrades to a single column on phones. Keyboard accessible, high-contrast, readable 14px+ text.
- On page unload, send a sendBeacon/fetch keepalive DELETE so the data is cleared.
- Never persist anything in the browser (no localStorage, cookies or IndexedDB).

TESTS (pytest with httpx TestClient, synthetic files built in memory): successful upload for each card then preview pagination boundaries; mismatch returns 422 and nothing is stored; export downloads a valid xlsx with the correct headers and values; session isolation (session B cannot read session A); DELETE wipes; missing or invalid session id returns 401; the no-disk test is still green with a realistic 5 MB upload through this route.

Run pytest, then start the app and tell me how you verified the page in the browser (desktop and a narrow viewport). Stop with a summary.