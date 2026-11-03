/**
 * CardLyze Client Session Manager & Shared Utilities
 * 
 * Strict Privacy Policy:
 * Session tokens are kept purely in JavaScript runtime memory (closure).
 * Never saved to localStorage, sessionStorage, cookies, or IndexedDB.
 */

(function (window) {
    'use strict';

    // In-memory token storage (ephemeral to the current page instance)
    let currentSessionId = null;
    let sessionInitPromise = null;

    /**
     * Initialize or retrieve an active session token lazily.
     * @returns {Promise<string>} session_id
     */
    async function initSession() {
        if (currentSessionId) {
            return currentSessionId;
        }

        if (sessionInitPromise) {
            return sessionInitPromise;
        }

        sessionInitPromise = (async () => {
            try {
                const response = await fetch('/api/session', {
                    method: 'POST',
                    headers: {
                        'Accept': 'application/json',
                    },
                });

                if (!response.ok) {
                    if (response.status === 503) {
                        throw new Error('Server is currently at maximum session capacity. Please try again shortly.');
                    }
                    throw new Error(`Failed to initialize session: HTTP ${response.status}`);
                }

                const data = await response.json();
                currentSessionId = data.session_id;

                updateSessionIndicator(true);
                return currentSessionId;
            } catch (err) {
                updateSessionIndicator(false);
                console.error('[CardLyze] Session initialization error:', err.message);
                throw err;
            } finally {
                sessionInitPromise = null;
            }
        })();

        return sessionInitPromise;
    }

    /**
     * Get the current in-memory session token.
     */
    function getSessionId() {
        return currentSessionId;
    }

    /**
     * Wipe session on server and reset local memory.
     */
    async function wipeSession() {
        if (!currentSessionId) return;

        const token = currentSessionId;
        currentSessionId = null;

        try {
            await fetch('/api/session', {
                method: 'DELETE',
                headers: {
                    'X-Session-Id': token,
                },
                keepalive: true,
            });
        } catch (e) {
            // Best effort during teardown
        } finally {
            updateSessionIndicator(false);
        }
    }

    /**
     * Authenticated fetch helper attaching X-Session-Id.
     */
    async function fetchWithSession(url, options = {}) {
        const sessionId = await initSession();
        const headers = new Headers(options.headers || {});
        headers.set('X-Session-Id', sessionId);

        return fetch(url, {
            ...options,
            headers,
        });
    }

    /**
     * Update session status dot in UI if present.
     */
    function updateSessionIndicator(isActive) {
        const dot = document.querySelector('.session-dot');
        const text = document.querySelector('.session-text');
        if (dot) {
            dot.classList.toggle('active', isActive);
        }
        if (text) {
            text.textContent = isActive ? 'Session Secure (In-Memory)' : 'Connecting Session...';
        }
    }

    /**
     * Auto-wipe session on page unload using keepalive fetch.
     * Skips DELETE if no session exists yet.
     */
    window.addEventListener('pagehide', function () {
        if (currentSessionId) {
            const token = currentSessionId;
            currentSessionId = null;
            try {
                fetch('/api/session', {
                    method: 'DELETE',
                    headers: { 'X-Session-Id': token },
                    keepalive: true,
                });
            } catch (e) {
                // Ignore during navigation
            }
        }
    });

    /**
     * Escape HTML string safely.
     */
    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    /**
     * Determine if a value is purely numeric.
     */
    function isNumeric(val) {
        if (val === null || val === undefined) return false;
        const str = String(val).trim();
        if (str === '') return false;
        return /^-?\d+(\.\d+)?$/.test(str);
    }

    /**
     * Reusable, High-Performance DataTable Component
     * 
     * Features:
     * - In-box scrolling (max-height ~60vh), sticky headers, sticky first column
     * - Server-side pagination (25, 50, 100)
     * - Column picker with live search, Select all, Clear, Key columns shortcuts
     * - Density toggle (Compact / Comfortable)
     * - Row detail side drawer with Copy All
     * - Fully CSP-compliant (0 inline styles, 0 inline scripts, 0 eval)
     */
    class DataTable {
        constructor(container, options = {}) {
            this.container = typeof container === 'string' ? document.querySelector(container) : container;
            if (!this.container) {
                throw new Error('DataTable: container element not found');
            }

            this.options = Object.assign({
                fetchData: null,
                hiddenColumns: [],
                keyColumns: [],
                initialPageSize: 25,
            }, options);

            this.allColumns = [];
            this.selectedColumns = new Set();
            this.currentPage = 1;
            this.pageSize = this.options.initialPageSize || 25;
            this.totalRows = 0;
            this.totalPages = 1;
            this.rows = [];
            this.selectedRow = null;
            this.selectedRowIndex = -1;
            this.isCompact = false;
            this.isLoading = false;

            this._initDom();
            this._bindEvents();

            if (options.initialData) {
                this.setData(options.initialData);
            }
        }

        _initDom() {
            this.container.classList.add('dt-root');

            // 1. Toolbar (Density, Column Picker, Meta summary)
            this.toolbarEl = document.createElement('div');
            this.toolbarEl.className = 'dt-toolbar';

            // Left actions: Density & Column Picker
            const leftActions = document.createElement('div');
            leftActions.className = 'dt-toolbar-left';

            // Density button
            this.densityBtn = document.createElement('button');
            this.densityBtn.type = 'button';
            this.densityBtn.className = 'btn btn-outline btn-sm dt-btn-density';
            this.densityBtn.setAttribute('aria-label', 'Toggle row density');
            this.densityBtn.innerHTML = '<span class="dt-icon">↕</span> <span class="dt-density-label">Compact</span>';
            leftActions.appendChild(this.densityBtn);

            // Column Picker Container
            this.colPickerContainer = document.createElement('div');
            this.colPickerContainer.className = 'dt-col-picker-container';

            this.colPickerBtn = document.createElement('button');
            this.colPickerBtn.type = 'button';
            this.colPickerBtn.className = 'btn btn-outline btn-sm dt-btn-col-picker';
            this.colPickerBtn.setAttribute('aria-expanded', 'false');
            this.colPickerBtn.setAttribute('aria-haspopup', 'true');
            this.colPickerBtn.innerHTML = '<span class="dt-icon">⚙</span> <span class="dt-col-picker-label">Columns</span> <span class="dt-caret">▼</span>';
            this.colPickerContainer.appendChild(this.colPickerBtn);

            // Column Picker Dropdown Menu
            this.colPickerMenu = document.createElement('div');
            this.colPickerMenu.className = 'dt-col-picker-menu hidden';

            // Picker Header with Search
            const pickerHeader = document.createElement('div');
            pickerHeader.className = 'dt-picker-header';

            this.colSearchInput = document.createElement('input');
            this.colSearchInput.type = 'text';
            this.colSearchInput.className = 'dt-picker-search';
            this.colSearchInput.placeholder = 'Search columns...';
            this.colSearchInput.setAttribute('aria-label', 'Search columns');
            pickerHeader.appendChild(this.colSearchInput);

            // Picker Shortcuts
            const pickerShortcuts = document.createElement('div');
            pickerShortcuts.className = 'dt-picker-shortcuts';

            this.btnSelectAllCols = document.createElement('button');
            this.btnSelectAllCols.type = 'button';
            this.btnSelectAllCols.className = 'dt-shortcut-btn';
            this.btnSelectAllCols.textContent = 'Select all';
            pickerShortcuts.appendChild(this.btnSelectAllCols);

            this.btnClearCols = document.createElement('button');
            this.btnClearCols.type = 'button';
            this.btnClearCols.className = 'dt-shortcut-btn';
            this.btnClearCols.textContent = 'Clear';
            pickerShortcuts.appendChild(this.btnClearCols);

            this.btnKeyCols = document.createElement('button');
            this.btnKeyCols.type = 'button';
            this.btnKeyCols.className = 'dt-shortcut-btn';
            this.btnKeyCols.textContent = 'Key columns';
            pickerShortcuts.appendChild(this.btnKeyCols);

            pickerHeader.appendChild(pickerShortcuts);
            this.colPickerMenu.appendChild(pickerHeader);

            // Checkbox list
            this.colPickerList = document.createElement('div');
            this.colPickerList.className = 'dt-picker-list';
            this.colPickerMenu.appendChild(this.colPickerList);

            this.colPickerContainer.appendChild(this.colPickerMenu);
            leftActions.appendChild(this.colPickerContainer);
            this.toolbarEl.appendChild(leftActions);

            // Right toolbar info
            this.toolbarRightEl = document.createElement('div');
            this.toolbarRightEl.className = 'dt-toolbar-right';
            this.infoSummaryEl = document.createElement('span');
            this.infoSummaryEl.className = 'dt-info-summary';
            this.toolbarRightEl.appendChild(this.infoSummaryEl);
            this.toolbarEl.appendChild(this.toolbarRightEl);

            this.container.appendChild(this.toolbarEl);

            // 2. Table Scroll Container
            this.scrollContainerEl = document.createElement('div');
            this.scrollContainerEl.className = 'dt-scroll-container';

            this.tableEl = document.createElement('table');
            this.tableEl.className = 'dt-table';
            this.theadEl = document.createElement('thead');
            this.tbodyEl = document.createElement('tbody');

            this.tableEl.appendChild(this.theadEl);
            this.tableEl.appendChild(this.tbodyEl);
            this.scrollContainerEl.appendChild(this.tableEl);

            // Loading overlay inside scroll container
            this.tableLoaderEl = document.createElement('div');
            this.tableLoaderEl.className = 'dt-table-loader hidden';
            this.tableLoaderEl.innerHTML = '<div class="progress-bar-indeterminate"></div><div class="dt-loader-text">Loading rows...</div>';
            this.scrollContainerEl.appendChild(this.tableLoaderEl);

            this.container.appendChild(this.scrollContainerEl);

            // 3. Pagination Bar
            this.paginationEl = document.createElement('div');
            this.paginationEl.className = 'dt-pagination';

            // Left: Showing X to Y of Z
            this.pageInfoEl = document.createElement('div');
            this.pageInfoEl.className = 'dt-page-info';
            this.paginationEl.appendChild(this.pageInfoEl);

            // Right: Page size selector and page navigation buttons
            const pageControls = document.createElement('div');
            pageControls.className = 'dt-page-controls';

            // Rows per page selector
            const sizeLabel = document.createElement('label');
            sizeLabel.className = 'dt-size-label';
            sizeLabel.textContent = 'Rows per page: ';

            this.pageSizeSelect = document.createElement('select');
            this.pageSizeSelect.className = 'dt-select dt-page-size-select';
            [25, 50, 100].forEach(size => {
                const opt = document.createElement('option');
                opt.value = size;
                opt.textContent = size;
                if (size === this.pageSize) opt.selected = true;
                this.pageSizeSelect.appendChild(opt);
            });
            sizeLabel.appendChild(this.pageSizeSelect);
            pageControls.appendChild(sizeLabel);

            // Navigation buttons: First, Prev, Page Display, Next, Last
            this.btnFirst = document.createElement('button');
            this.btnFirst.type = 'button';
            this.btnFirst.className = 'btn btn-outline btn-sm dt-btn-nav';
            this.btnFirst.innerHTML = '&laquo;';
            this.btnFirst.title = 'First page';
            this.btnFirst.setAttribute('aria-label', 'First page');
            pageControls.appendChild(this.btnFirst);

            this.btnPrev = document.createElement('button');
            this.btnPrev.type = 'button';
            this.btnPrev.className = 'btn btn-outline btn-sm dt-btn-nav';
            this.btnPrev.innerHTML = '&lsaquo;';
            this.btnPrev.title = 'Previous page';
            this.btnPrev.setAttribute('aria-label', 'Previous page');
            pageControls.appendChild(this.btnPrev);

            this.pageIndicator = document.createElement('span');
            this.pageIndicator.className = 'dt-page-indicator';
            this.pageIndicator.textContent = 'Page 1 of 1';
            pageControls.appendChild(this.pageIndicator);

            this.btnNext = document.createElement('button');
            this.btnNext.type = 'button';
            this.btnNext.className = 'btn btn-outline btn-sm dt-btn-nav';
            this.btnNext.innerHTML = '&rsaquo;';
            this.btnNext.title = 'Next page';
            this.btnNext.setAttribute('aria-label', 'Next page');
            pageControls.appendChild(this.btnNext);

            this.btnLast = document.createElement('button');
            this.btnLast.type = 'button';
            this.btnLast.className = 'btn btn-outline btn-sm dt-btn-nav';
            this.btnLast.innerHTML = '&raquo;';
            this.btnLast.title = 'Last page';
            this.btnLast.setAttribute('aria-label', 'Last page');
            pageControls.appendChild(this.btnLast);

            this.paginationEl.appendChild(pageControls);
            this.container.appendChild(this.paginationEl);

            // 4. Row Detail Drawer (Slide-out panel)
            this.drawerOverlayEl = document.createElement('div');
            this.drawerOverlayEl.className = 'dt-drawer-overlay hidden';

            this.drawerEl = document.createElement('aside');
            this.drawerEl.className = 'dt-drawer';
            this.drawerEl.setAttribute('role', 'dialog');
            this.drawerEl.setAttribute('aria-label', 'Row Details');

            const drawerHeader = document.createElement('div');
            drawerHeader.className = 'dt-drawer-header';

            this.drawerTitleEl = document.createElement('h3');
            this.drawerTitleEl.className = 'dt-drawer-title';
            this.drawerTitleEl.textContent = 'Row Details';
            drawerHeader.appendChild(this.drawerTitleEl);

            const drawerActions = document.createElement('div');
            drawerActions.className = 'dt-drawer-actions';

            this.btnCopyRow = document.createElement('button');
            this.btnCopyRow.type = 'button';
            this.btnCopyRow.className = 'btn btn-outline btn-sm dt-btn-copy';
            this.btnCopyRow.textContent = 'Copy All';
            this.btnCopyRow.title = 'Copy all fields as text';
            drawerActions.appendChild(this.btnCopyRow);

            this.btnCloseDrawer = document.createElement('button');
            this.btnCloseDrawer.type = 'button';
            this.btnCloseDrawer.className = 'btn btn-outline btn-sm dt-btn-close';
            this.btnCloseDrawer.innerHTML = '&times;';
            this.btnCloseDrawer.title = 'Close details (Esc)';
            this.btnCloseDrawer.setAttribute('aria-label', 'Close details');
            drawerActions.appendChild(this.btnCloseDrawer);

            drawerHeader.appendChild(drawerActions);
            this.drawerEl.appendChild(drawerHeader);

            this.drawerBodyEl = document.createElement('div');
            this.drawerBodyEl.className = 'dt-drawer-body';
            this.drawerEl.appendChild(this.drawerBodyEl);

            this.drawerOverlayEl.appendChild(this.drawerEl);
            document.body.appendChild(this.drawerOverlayEl);
        }

        _bindEvents() {
            // Density Toggle
            this.densityBtn.addEventListener('click', () => {
                this.isCompact = !this.isCompact;
                this.tableEl.classList.toggle('dt-compact', this.isCompact);
                const label = this.densityBtn.querySelector('.dt-density-label');
                if (label) {
                    label.textContent = this.isCompact ? 'Comfortable' : 'Compact';
                }
            });

            // Column Picker Toggle
            this.colPickerBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const isOpen = !this.colPickerMenu.classList.contains('hidden');
                if (isOpen) {
                    this._closeColPicker();
                } else {
                    this._openColPicker();
                }
            });

            // Close picker when clicking outside
            document.addEventListener('click', (e) => {
                if (!this.colPickerContainer.contains(e.target)) {
                    this._closeColPicker();
                }
            });

            // Column Search Filter
            this.colSearchInput.addEventListener('input', () => {
                const query = this.colSearchInput.value.toLowerCase().trim();
                const items = this.colPickerList.querySelectorAll('.dt-picker-item');
                items.forEach(item => {
                    const text = item.textContent.toLowerCase();
                    item.classList.toggle('hidden', query.length > 0 && !text.includes(query));
                });
            });

            // Shortcuts
            this.btnSelectAllCols.addEventListener('click', () => {
                this.allColumns.forEach(c => this.selectedColumns.add(c));
                this._updateColPickerCheckboxes();
                this._renderHeaders();
                this._renderRows();
            });

            this.btnClearCols.addEventListener('click', () => {
                // Keep at least the first column selected to avoid a totally empty table
                this.selectedColumns.clear();
                if (this.allColumns.length > 0) {
                    this.selectedColumns.add(this.allColumns[0]);
                }
                this._updateColPickerCheckboxes();
                this._renderHeaders();
                this._renderRows();
            });

            this.btnKeyCols.addEventListener('click', () => {
                this.selectedColumns.clear();
                const keys = (this.options.keyColumns && this.options.keyColumns.length > 0)
                    ? this.options.keyColumns
                    : this.allColumns.slice(0, 5);
                keys.forEach(k => {
                    if (this.allColumns.includes(k)) {
                        this.selectedColumns.add(k);
                    }
                });
                if (this.selectedColumns.size === 0 && this.allColumns.length > 0) {
                    this.selectedColumns.add(this.allColumns[0]);
                }
                this._updateColPickerCheckboxes();
                this._renderHeaders();
                this._renderRows();
            });

            // Rows per page change
            this.pageSizeSelect.addEventListener('change', () => {
                this.pageSize = parseInt(this.pageSizeSelect.value, 10);
                this.currentPage = 1;
                this._requestData();
            });

            // Pagination buttons
            this.btnFirst.addEventListener('click', () => {
                if (this.currentPage > 1) {
                    this.currentPage = 1;
                    this._requestData();
                }
            });

            this.btnPrev.addEventListener('click', () => {
                if (this.currentPage > 1) {
                    this.currentPage--;
                    this._requestData();
                }
            });

            this.btnNext.addEventListener('click', () => {
                if (this.currentPage < this.totalPages) {
                    this.currentPage++;
                    this._requestData();
                }
            });

            this.btnLast.addEventListener('click', () => {
                if (this.currentPage < this.totalPages) {
                    this.currentPage = this.totalPages;
                    this._requestData();
                }
            });

            // Drawer Close
            this.btnCloseDrawer.addEventListener('click', () => this.closeDrawer());
            this.drawerOverlayEl.addEventListener('click', (e) => {
                if (e.target === this.drawerOverlayEl) {
                    this.closeDrawer();
                }
            });

            // Drawer Copy All
            this.btnCopyRow.addEventListener('click', async () => {
                if (!this.selectedRow) return;
                const lines = this.allColumns.map(col => {
                    const val = this.selectedRow[col];
                    return `${col}: ${val !== undefined && val !== null ? val : ''}`;
                });
                const text = lines.join('\n');
                try {
                    if (navigator.clipboard && navigator.clipboard.writeText) {
                        await navigator.clipboard.writeText(text);
                    } else {
                        const ta = document.createElement('textarea');
                        ta.value = text;
                        ta.className = 'dt-clipboard-fallback';
                        document.body.appendChild(ta);
                        ta.select();
                        document.execCommand('copy');
                        document.body.removeChild(ta);
                    }
                    this.btnCopyRow.textContent = 'Copied!';
                    setTimeout(() => {
                        this.btnCopyRow.textContent = 'Copy All';
                    }, 2000);
                } catch (err) {
                    console.error('Clipboard copy error:', err);
                }
            });

            // ESC to close drawer or picker
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    this._closeColPicker();
                    this.closeDrawer();
                }
            });
        }

        _openColPicker() {
            this.colPickerMenu.classList.remove('hidden');
            this.colPickerBtn.setAttribute('aria-expanded', 'true');
            this.colSearchInput.value = '';
            this.colSearchInput.focus();
            const items = this.colPickerList.querySelectorAll('.dt-picker-item');
            items.forEach(i => i.classList.remove('hidden'));
        }

        _closeColPicker() {
            this.colPickerMenu.classList.add('hidden');
            this.colPickerBtn.setAttribute('aria-expanded', 'false');
        }

        _updateColPickerSummary() {
            const countLabel = this.colPickerBtn.querySelector('.dt-col-picker-label');
            if (countLabel) {
                countLabel.textContent = `Columns (${this.selectedColumns.size}/${this.allColumns.length})`;
            }
        }

        _buildColPickerList() {
            this.colPickerList.innerHTML = '';
            this.allColumns.forEach(col => {
                const label = document.createElement('label');
                label.className = 'dt-picker-item';

                const cb = document.createElement('input');
                cb.type = 'checkbox';
                cb.className = 'dt-picker-checkbox';
                cb.checked = this.selectedColumns.has(col);
                cb.dataset.column = col;

                cb.addEventListener('change', () => {
                    if (cb.checked) {
                        this.selectedColumns.add(col);
                    } else {
                        // Prevent unchecking all columns
                        if (this.selectedColumns.size > 1) {
                            this.selectedColumns.delete(col);
                        } else {
                            cb.checked = true; // revert
                        }
                    }
                    this._updateColPickerSummary();
                    this._renderHeaders();
                    this._renderRows();
                });

                label.appendChild(cb);
                const span = document.createElement('span');
                span.className = 'dt-picker-col-name';
                span.textContent = col;
                label.appendChild(span);

                this.colPickerList.appendChild(label);
            });

            this._updateColPickerSummary();
        }

        _updateColPickerCheckboxes() {
            const checkboxes = this.colPickerList.querySelectorAll('.dt-picker-checkbox');
            checkboxes.forEach(cb => {
                cb.checked = this.selectedColumns.has(cb.dataset.column);
            });
            this._updateColPickerSummary();
        }

        setData(data) {
            // Expected shape: { page, page_size, total_rows, total_pages, columns, rows }
            if (!data) return;

            const hiddenSet = new Set(this.options.hiddenColumns || []);
            this.allColumns = (data.columns || []).filter(c => !c.startsWith('_raw_') && !hiddenSet.has(c));

            // Default all columns selected initially if not already initialized
            if (this.selectedColumns.size === 0) {
                this.allColumns.forEach(c => this.selectedColumns.add(c));
            } else {
                // prune columns that no longer exist
                const valid = new Set(this.allColumns);
                for (const c of this.selectedColumns) {
                    if (!valid.has(c)) this.selectedColumns.delete(c);
                }
                if (this.selectedColumns.size === 0) {
                    this.allColumns.forEach(c => this.selectedColumns.add(c));
                }
            }

            this.currentPage = data.page || 1;
            this.pageSize = data.page_size || this.pageSize;
            this.totalRows = data.total_rows || (data.rows ? data.rows.length : 0);
            this.totalPages = data.total_pages || Math.max(1, Math.ceil(this.totalRows / this.pageSize));
            this.rows = data.rows || [];

            this._buildColPickerList();
            this._renderHeaders();
            this._renderRows();
            this._renderPagination();
        }

        _renderHeaders() {
            this.theadEl.innerHTML = '';
            const tr = document.createElement('tr');

            // Render visible columns
            this.allColumns.forEach((col, idx) => {
                if (!this.selectedColumns.has(col)) return;

                const th = document.createElement('th');
                th.className = 'dt-th';
                if (idx === 0) th.classList.add('dt-th-sticky-first');
                th.textContent = col;
                th.title = col;
                tr.appendChild(th);
            });

            this.theadEl.appendChild(tr);
        }

        _renderRows() {
            this.tbodyEl.innerHTML = '';

            if (this.rows.length === 0) {
                const tr = document.createElement('tr');
                const td = document.createElement('td');
                td.colSpan = Math.max(1, this.selectedColumns.size);
                td.className = 'dt-empty-message';
                td.textContent = 'No records found.';
                tr.appendChild(td);
                this.tbodyEl.appendChild(tr);
                return;
            }

            this.rows.forEach((row, rowIdx) => {
                const tr = document.createElement('tr');
                tr.className = 'dt-row';
                tr.dataset.rowIndex = rowIdx;
                tr.setAttribute('tabindex', '0');
                tr.setAttribute('role', 'button');
                tr.setAttribute('aria-label', `View details for row ${rowIdx + 1}`);

                if (this.selectedRowIndex === rowIdx) {
                    tr.classList.add('dt-row-selected');
                }

                // Render visible cells
                this.allColumns.forEach((col, colIdx) => {
                    if (!this.selectedColumns.has(col)) return;

                    const td = document.createElement('td');
                    td.className = 'dt-td';
                    if (colIdx === 0) td.classList.add('dt-td-sticky-first');

                    const rawVal = row[col];
                    if (rawVal === null || rawVal === undefined || String(rawVal).trim() === '') {
                        const dash = document.createElement('span');
                        dash.className = 'dt-empty-dash';
                        dash.textContent = '—';
                        td.appendChild(dash);
                    } else {
                        const strVal = String(rawVal).trim();
                        td.textContent = strVal;
                        td.title = strVal;
                        if (isNumeric(strVal)) {
                            td.classList.add('dt-cell-num');
                        } else {
                            td.classList.add('dt-cell-text');
                        }
                    }

                    tr.appendChild(td);
                });

                // Row click -> opens drawer
                tr.addEventListener('click', () => {
                    this.openDrawer(row, rowIdx);
                });

                // Keyboard Enter/Space on row -> opens drawer
                tr.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        this.openDrawer(row, rowIdx);
                    }
                });

                this.tbodyEl.appendChild(tr);
            });
        }

        _renderPagination() {
            const start = this.totalRows === 0 ? 0 : (this.currentPage - 1) * this.pageSize + 1;
            const end = Math.min(this.currentPage * this.pageSize, this.totalRows);
            this.pageInfoEl.textContent = `Showing ${start.toLocaleString()} to ${end.toLocaleString()} of ${this.totalRows.toLocaleString()} rows`;

            this.pageIndicator.textContent = `Page ${this.currentPage} of ${this.totalPages}`;
            this.pageSizeSelect.value = this.pageSize;

            this.btnFirst.disabled = this.currentPage <= 1 || this.isLoading;
            this.btnPrev.disabled = this.currentPage <= 1 || this.isLoading;
            this.btnNext.disabled = this.currentPage >= this.totalPages || this.isLoading;
            this.btnLast.disabled = this.currentPage >= this.totalPages || this.isLoading;
        }

        async _requestData() {
            if (!this.options.fetchData) return;

            this.isLoading = true;
            this.tableLoaderEl.classList.remove('hidden');
            this.btnFirst.disabled = true;
            this.btnPrev.disabled = true;
            this.btnNext.disabled = true;
            this.btnLast.disabled = true;

            try {
                const data = await this.options.fetchData(this.currentPage, this.pageSize);
                this.setData(data);
            } catch (err) {
                console.error('DataTable fetch error:', err);
            } finally {
                this.isLoading = false;
                this.tableLoaderEl.classList.add('hidden');
                this._renderPagination();
            }
        }

        openDrawer(row, rowIdx) {
            this.selectedRow = row;
            this.selectedRowIndex = rowIdx;

            // Highlight row in table
            const allRows = this.tbodyEl.querySelectorAll('.dt-row');
            allRows.forEach(r => r.classList.remove('dt-row-selected'));
            const targetRow = this.tbodyEl.querySelector(`[data-row-index="${rowIdx}"]`);
            if (targetRow) {
                targetRow.classList.add('dt-row-selected');
            }

            const absRowNumber = (this.currentPage - 1) * this.pageSize + rowIdx + 1;
            this.drawerTitleEl.textContent = `Row Details (#${absRowNumber.toLocaleString()})`;

            // Populate fields
            this.drawerBodyEl.innerHTML = '';
            this.allColumns.forEach(col => {
                const item = document.createElement('div');
                item.className = 'dt-drawer-field';

                const label = document.createElement('div');
                label.className = 'dt-drawer-label';
                label.textContent = col;
                item.appendChild(label);

                const valEl = document.createElement('div');
                valEl.className = 'dt-drawer-value';
                const val = row[col];
                if (val === null || val === undefined || String(val).trim() === '') {
                    valEl.innerHTML = '<span class="dt-empty-dash">—</span>';
                } else {
                    valEl.textContent = String(val);
                }
                item.appendChild(valEl);

                this.drawerBodyEl.appendChild(item);
            });

            this.drawerOverlayEl.classList.remove('hidden');
            this.drawerEl.classList.add('open');
            this.btnCloseDrawer.focus();
        }

        closeDrawer() {
            this.drawerEl.classList.remove('open');
            this.drawerOverlayEl.classList.add('hidden');
            this.selectedRow = null;
            this.selectedRowIndex = -1;

            const allRows = this.tbodyEl.querySelectorAll('.dt-row');
            allRows.forEach(r => r.classList.remove('dt-row-selected'));
        }
    }

    // Expose CardLyze namespace and DataTable globally
    window.CardLyze = {
        initSession,
        getSessionId,
        wipeSession,
        fetchWithSession,
        escapeHtml,
        isNumeric,
        DataTable,
    };
    window.DataTable = DataTable;

})(window);
