Read SPEC.md first. Build the Analysis page UI (static/analysis.html, js/analysis.js) on top of the Phase 4 API, reusing the DataTable component from Phase 3. Priorities: readability and efficiency. Keep it simple, with no libraries.

FLOW
1. Choose card source first (three large options), then upload the Excel file (drop zone or button, under 50 MB, progress indicator, clear error messages for wrong headers).
2. After load, show a compact summary bar: file name, total rows, matching rows (updates live), date range, and any parse warnings as a collapsible notice (counts only).

LAYOUT (desktop)
- Left sidebar (collapsible) with: Filters; on narrow screens it becomes a slide-over drawer opened by a "Filters" button.
- Main area: toolbar, then the table.

FILTER CONTROLS
- Country code and MCC are pinned at the top of the sidebar as two multi-select filters. Each shows a searchable checklist of values with counts, Include/Exclude toggle, "Select all shown" and "Clear". The list uses the faceted /unique endpoint and loads more on scroll or with a "Load more" button.
- "Add filter on any column": a column dropdown (searchable) that opens the same checklist control for that column. Active filters show as removable chips above the table; "Clear all filters" button.
- Global search box (debounced about 300 ms) with a scope selector: "Visible columns" or one chosen column. A clear (x) button.

COLUMN CONTROL
- "Columns" dropdown (from the shared DataTable): checkbox list with search, presets "Key columns" (default), "All", "None". Sensitive columns are unchecked by default and carry a small lock label.

UNIQUE VALUES
- "Explore column" dropdown: pick any column to open a panel with the stats for that column (from the stats endpoint), total unique count, blank count, and the full list of unique values with counts, searchable, loading in chunks, with a "Show all (N)" action that keeps loading. Clicking a value offers "Filter to this" or "Exclude this". A "Copy list" button.

TABLE
- Sortable by clicking headers (server-side), pagination, row detail panel, sticky header and first column, numeric columns right-aligned with thousands separators, dates as YYYY-MM-DD, IDs and card or account numbers always shown as plain text (never reformatted), blanks as a faint dash.

EXPORT
- "Export to Excel" exports the current filters and visible columns. Show the row count that will be exported and warn before very large exports. Also "Clear data" button which wipes the session data and resets the page; also clear on page unload via a keepalive request.

QUALITY
- Responsive from tablet to desktop, graceful on phone. Keyboard accessible, visible focus states, readable contrast, loading and empty states ("No rows match these filters" with a clear-filters link). Cancel stale requests when the user types or changes filters quickly (AbortController) so the table never shows out-of-date results.
- Nothing stored in the browser (no localStorage, cookies or IndexedDB). No external requests.

TESTS: add pytest tests for any new backend glue and a lightweight smoke test that the static pages are served with the right headers and contain the expected controls (IDs). Then manually verify in a browser with a synthetic file for each of the three cards (desktop width and about 390 px width) and report what you checked.

Run pytest and show results. Stop with a summary.