Read SPEC.md first. Build the Analysis backend (no UI yet). Same privacy rules: in memory only, raw-body upload, per-session storage, no cell values in logs or error messages. Respect the local-laptop limits already in config (max sessions 2, 1 parallel parse, 1 parallel export, loopback-only binding). Target: a real VISA file of ~155k rows x 29 columns (25 MB) must load, filter and export on a 6 GB RAM laptop.

REUSE, DON'T REBUILD
- services/typing.py already has apply_card_typing (numeric coercion, explicit-format dates, id-like text, padding with _raw_<col> originals, country_code, mcc_code/mcc_description, quality notes). The upload route must call it, not duplicate it. Extend it only if something below needs it.
- Reuse read_excel_bytes (calamine first), read_limited_body, run_parse_task, and the optimized to_xlsx_buffer / iter_csv_chunks from services/headers.py.
- All heavy work (parse, typing, query, unique, stats, export) runs in the threadpool behind the existing semaphores. The event loop and /api/health must never block.

UPLOAD: POST /api/analysis/{card_key}/upload (raw body, max 50 MB, .xlsx only). The file already has headers.
 1. Read with header=0, dtype=str. Verify headers match the card's expected_columns; report missing and extra columns clearly by NAME (column names are not cell values, so this is allowed). Drop all-empty rows with a fast vectorised check (the current apply/astype(str) mask costs ~2 s per 150k rows; replace it if you can do so safely).
 2. Run apply_card_typing. Never mutate original strings in place.
 3. Store in session.analysis: the typed DataFrame, card_key, filename, and the typing metadata. Hold the _raw_<col> originals only for padded columns, never in any response.
 4. Memory discipline: convert low-cardinality text columns (e.g. country_code, mcc_code, currency, flags, card/type columns; use a threshold like unique/rows < 5% or <= 5000 uniques) to category dtype. Do not materialise a string-label copy of every column. See LABEL VIEW below.
 5. Return: row count, parse time, per-column info {name, type (text/number/date), null_pct, unique_count, is_key, is_sensitive, is_derived}, parse warnings as counts and structural shapes per column (never values), date min/max per date column, country_summary, padding_notes, dob/rrn quality notes, country_confidence, plus key_cols and sensitive_cols lists so the UI can set default columns. Report that only the first sheet was read if the workbook has several.

LABEL VIEW (shared by query, unique, stats, search, export)
- A label is the string form of a column used for matching: blanks (NaN/null tokens/empty) are "(blank)", dates are YYYY-MM-DD, numbers use a stable plain format (no scientific notation), ids stay exact text.
- Build labels LAZILY per column, on first use, and cache them in the session in a small LRU (e.g. at most 4 columns or a byte cap). Category columns can compute counts and filters on categories directly. Cross-column search over the display columns must work without building all 29 label columns at once (process column by column, OR the masks, free as you go).
- Report approximate session memory (df.memory_usage(deep=True) sum, in MB) in the upload response.

QUERY: POST /api/analysis/query with JSON {filters:[{column, mode:"include"|"exclude", values:[...]}], search:{text, column|null}, columns:[...], sort:{column, dir}|null, page, page_size}. Returns {total_rows, matching_rows, rows, page info}. Rules:
 - Filters are ANDed; matching uses the label view. Values are matched exactly against labels.
 - Search: case-insensitive, whitespace-insensitive (reuse collapse_whitespace/search logic from cards.py) substring with regex=False over the chosen column, or over the currently selected display columns when column is null. Cap search text at 100 chars; reject unknown columns with a clear error that does not echo values.
 - country_code and mcc_code are normal filter columns, no special-casing in the engine. mcc display value is "code - description" via format_mcc_display.
 - Sort server-side. Sort numbers and dates by their typed values (blanks last), text by label, case-insensitively, with a stable tiebreak on original row order.
 - Return only the requested columns and page (page_size 25/50/100); never the full frame. Rows are JSON-safe: numbers as numbers or exact text, dates as YYYY-MM-DD, IDs as text exactly as stored, blanks as "".
 - Cache the last filtered index per session keyed by a hash of (filters, search) so paging and sorting are fast. Invalidate on a new upload or DELETE.
 - Validate every input (unknown columns, page bounds, oversized values list) with clear 422 messages.

UNIQUE VALUES: POST /api/analysis/unique with {column, filters, search, value_search, offset, limit}. Returns {total_unique, blank_count, values:[{value, count}], has_more}, sorted by count desc then value. FACETED: apply all active filters and search EXCEPT the filter on the same column. Support value_search (case-insensitive substring on the label) and paging; limit up to 500 per call. Cache nothing that stores raw values outside the session.

COLUMN STATS: POST /api/analysis/stats with {column, filters, search} (POST so current filters apply; GET /api/analysis/stats?column= may remain as a convenience for unfiltered stats). Numbers: min, max, mean, sum, count, blank count. Dates: min, max, blank count. Text: unique count, blank count, top 5 values with counts. All computed on the matching rows.

EXPORT: POST /api/analysis/export with the same body as query minus paging, plus format: "csv" (default) | "xlsx".
 - CSV: streaming in chunks of ~20,000 rows via the existing chunked pattern (UTF-8 BOM on chunk 1, header once, CRLF, no full-file buffer), filename {card}_analysis_{YYYYMMDD}.csv. This is the recommended path for large results.
 - XLSX: reuse the optimized buffer writer, with write_string everywhere (formulas, URLs and numbers never auto-converted; IDs keep leading zeros). Refuse with a clear 422 if the row count exceeds 1,048,575 data rows. Return a warning field or header value when rows > 60,000 so the UI can warn that Excel export can take minutes.
 - Both formats: export only the matching rows and the requested columns, in the requested order; sensitive columns only if explicitly requested; never _raw_ columns. Dates as YYYY-MM-DD; numbers and IDs written as exact text/number consistent with the display. Honour the 1-parallel-export limit with a clear 503 when busy.
 - Add a GET /api/analysis/export-info (or include it in the query response) giving the row count that would be exported, so the UI can show it before the user commits.

DELETE /api/analysis wipes the dataset and caches. Wiping the session also drops them.

ERRORS (friendly, no values): corrupt or password-protected file, empty file, wrong extension, wrong or missing headers (list column names), expired session (401), busy (503), oversize (413). Log metadata only (card, byte count, row count, duration).

TESTS (synthetic data generated in the test, all 3 cards, never real data):
 - upload: type conversion and warning counts; explicit dates (03/04/2026 PineLabs is 3 April; dd-mm-yyyy Vegapay; VISA spdate 7-digit padding); ids and leading zeros preserved; wrong, missing and extra headers rejected with names; second upload replaces the first; response never contains offending values.
 - query: include, exclude, combined filters, blank handling ("(blank)"), search in one column, search across selected columns, whitespace-insensitive search, sorting for number, date and text columns, pagination bounds, cache hit gives identical results, cache invalidated by a new upload.
 - unique: faceted counts (selecting country=GB still lists other countries), value_search, paging with has_more, blank_count, ordering.
 - stats: number, date, text cases, with and without filters.
 - export: CSV respects filters and columns and order; BOM present; leading zeros and "=1+1" survive literally in both formats (read back with openpyxl and csv); xlsx row-limit refusal (monkeypatch the limit rather than generating a million rows); sensitive columns excluded unless requested; _raw_ columns never exported.
 - isolation and lifecycle: session B cannot read session A's analysis data; 401 on missing or invalid session; DELETE wipes; session cap respected; heavy endpoints do not block /api/health.
 - privacy: the no-disk test stays green with a realistic upload plus query plus CSV and xlsx export; no cell values appear in captured logs or error responses; security headers present on every analysis response; CSP and JS hygiene tests still green.
 - memory: a test asserting the category conversion happens for low-cardinality columns and that building labels for one column does not create labels for all columns.
 - slow (pytest -m slow): ~300k generated rows, print and assert generous thresholds for upload, query with 2 filters, unique on a high-cardinality column, stats, and CSV export TTFB.

REAL-DATA BENCHMARK SCRIPT (not a test, not committed with data): scratch/analysis_bench_real.py <path> <card> parses the file through the same upload code path and prints ONLY timings and memory: parse+typing time, frame memory MB, peak RSS, then latency of a typical query, a faceted unique on country_code and on the MCC column, a stats call, and CSV export TTFB and total time. Never print cell values.

Do not add UI. Do not add claims such as "100% fidelity" to any copy; report only measured values.

Run pytest (and pytest -m slow) and show results. Stop with a summary, and list assumptions I must confirm against real data: country_code derivation for VISA (last token of spldes) and PineLabs (trailing alpha-3), explicit date formats for PineLabs and VISA spbusd, the key and sensitive column lists, the category-dtype thresholds, and the label formats for numbers.