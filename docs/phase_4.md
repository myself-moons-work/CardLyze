Read SPEC.md first. Build the Analysis backend (no UI yet). Same privacy rules: in memory only, raw-body upload, per-session storage.

UPLOAD: POST /api/analysis/{card_key}/upload (raw body, max 50 MB, .xlsx only). The file already has headers. Steps:
 1. Read with dtype=str. Verify the headers match the card's expected_columns (report missing or extra columns clearly).
 2. Convert numeric_cols with pd.to_numeric(errors="coerce") and date_cols using the explicit candidate-format lists from cards.py (try each format, no guessing). id_like_cols stay text.
 3. Add the derived country_code column. Keep all conversion in a service module (services/typing.py).
 4. Return metadata: row count; per-column info {name, type (text/number/date), null_pct, unique_count, is_key, is_sensitive}; parse warnings as counts per column (never include the offending values); date min/max per date column.
 Never mutate the original strings in place: keep a text-label view for matching.

QUERY: POST /api/analysis/query with JSON {filters:[{column, mode:"include"|"exclude", values:[...]}], search:{text, column|null}, columns:[...], sort:{column, dir}|null, page, page_size}. Returns {total_rows, matching_rows, rows, page info}. Rules:
 - Matching uses a string label per column: blanks are the label "(blank)", dates are ISO formatted. Filters are ANDed.
 - Search is case-insensitive substring (regex=False) over the chosen column, or over the currently selected display columns when column is null. Cap the search text at 100 chars.
 - country_code and the card's MCC column are normal filter columns; no special-casing is needed in the engine.
 - Return only the requested columns and page; never the full frame.
 - Cache the last computed filtered index in the session keyed by a hash of (filters, search), so paging and sorting are fast.

UNIQUE VALUES: POST /api/analysis/unique with {column, filters, search, value_search, offset, limit}. Returns {total_unique, blank_count, values:[{value, count}], has_more}, sorted by count desc then value. IMPORTANT faceted behaviour: apply all active filters EXCEPT the filter on the same column, so after choosing country=GB the country list still shows other countries to add. Support value_search (substring on the value) and paging so "show all unique values" can load in chunks of 500.

COLUMN STATS: GET /api/analysis/stats?column= returns for numbers min, max, mean, sum, count; for dates min and max; for text unique count and top 5 values. Use the current filters via POST if simpler.

EXPORT: POST /api/analysis/export with the same body as query minus paging, returns an xlsx stream from memory with the filtered rows and the chosen columns only. Refuse with a clear message if the row count would exceed Excel's limit.

DELETE /api/analysis wipes the dataset.

TESTS (synthetic data generated in the test, 3 cards): type conversion and warning counts; explicit date formats parse dd/mm correctly (e.g. 03/04/2026 is 3 April, not March 4); include and exclude filters, combined filters, blank handling, search in one column and across selected columns; faceted unique counts behave as described; value_search and paging; sorting; export respects filters and columns; wrong headers rejected; sensitive/no-disk test still green; a marked-slow performance test (pytest -m slow) with about 300k generated rows asserting query and unique calls return in a reasonable time (set generous thresholds and print timings).

Run pytest and show results. Stop with a summary, and list any assumptions about country_code derivation and date formats I must confirm against real data.