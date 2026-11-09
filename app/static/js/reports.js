/**
 * TMS Reports & Archive Hub Frontend Controller.
 * 
 * Strict CSP & Hygiene Standards:
 * - 0 inline event handlers
 * - 0 inline style attributes or setAttribute('style')
 * - 0 eval or new Function
 * - 0 innerHTML assignments (pure createElement and textContent)
 * - Safe Blob URL download handling
 */

(function (window, document) {
    'use strict';

    // State Variables
    let overviewData = null;
    let currentWatchlistFilter = 'breached';
    let currentArchiveCardFilter = 'all';

    // DOM Elements
    const notificationBanner = document.getElementById('notification-banner');
    const notificationMessage = document.getElementById('notification-message');
    const notificationIcon = document.getElementById('notification-icon');
    const notificationDismiss = document.getElementById('notification-dismiss');

    const hubSimDate = document.getElementById('hub-sim-date');
    const hubSimCard = document.getElementById('hub-sim-card');
    const hubBtnRunBatch = document.getElementById('hub-btn-run-batch');
    const hubBatchSpinner = document.getElementById('hub-batch-spinner');

    const filterBreached = document.getElementById('filter-breached');
    const filterEmerging = document.getElementById('filter-emerging');
    const filterAll = document.getElementById('filter-all');
    const cumulativeWatchlistTbody = document.getElementById('cumulative-watchlist-tbody');

    const archiveCardFilter = document.getElementById('archive-card-filter');
    const btnRefreshArchive = document.getElementById('btn-refresh-archive');
    const dailyArchiveTbody = document.getElementById('daily-archive-tbody');

    // Modal elements
    const reportModal = document.getElementById('report-modal');
    const modalTitle = document.getElementById('modal-title');
    const modalSubtitle = document.getElementById('modal-subtitle');
    const modalBody = document.getElementById('modal-body');
    const btnModalClose = document.getElementById('btn-modal-close');
    const btnModalDismiss = document.getElementById('btn-modal-dismiss');
    const btnModalDownload = document.getElementById('btn-modal-download');

    let currentModalDownloadUrl = '';
    let currentModalDownloadFilename = '';

    // --- Notification Helpers ---
    function showNotification(type, message) {
        if (!notificationBanner) return;
        notificationBanner.className = 'notification-banner ' + type;
        if (notificationMessage) {
            notificationMessage.textContent = message;
        }
        if (notificationIcon) {
            notificationIcon.textContent = type === 'error' ? '✕' : (type === 'success' ? '✓' : 'i');
        }
    }

    if (notificationDismiss) {
        notificationDismiss.addEventListener('click', () => {
            if (notificationBanner) notificationBanner.className = 'notification-banner hidden';
        });
    }

    function formatBytes(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    // --- Modal Management ---
    function closeModal() {
        if (reportModal) {
            reportModal.classList.add('hidden');
        }
    }

    if (btnModalClose) btnModalClose.addEventListener('click', closeModal);
    if (btnModalDismiss) btnModalDismiss.addEventListener('click', closeModal);
    if (reportModal) {
        reportModal.addEventListener('click', (e) => {
            if (e.target === reportModal) closeModal();
        });
    }
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && reportModal && !reportModal.classList.contains('hidden')) {
            closeModal();
        }
    });

    if (btnModalDownload) {
        btnModalDownload.addEventListener('click', () => {
            if (currentModalDownloadUrl) {
                const a = document.createElement('a');
                a.href = currentModalDownloadUrl;
                a.setAttribute('download', currentModalDownloadFilename || 'report.xlsx');
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            }
        });
    }

    function openModalForReport(rep) {
        if (!rep) return;

        const cardUpper = (rep.card || 'REPORT').toUpperCase();
        const dateStr = rep.date || '--';

        if (modalTitle) {
            modalTitle.textContent = `${cardUpper} - Daily Report Details (${dateStr})`;
        }

        if (modalSubtitle) {
            modalSubtitle.textContent = rep.is_clean
                ? 'Status: Clean Day (0 Flagged Transactions)'
                : `${rep.flagged_transactions_count} Flagged Transactions | ${rep.flagged_individuals_count} Individual(s) | USD $${Number(rep.total_usd_volume || 0).toLocaleString()}`;
        }

        if (btnModalDownload) {
            if (!rep.is_clean) {
                btnModalDownload.classList.remove('hidden');
                currentModalDownloadUrl = `/api/task1/automated/download/daily/${encodeURIComponent(rep.filename)}`;
                currentModalDownloadFilename = rep.filename;
            } else {
                btnModalDownload.classList.add('hidden');
                currentModalDownloadUrl = '';
                currentModalDownloadFilename = '';
            }
        }

        if (modalBody) {
            while (modalBody.firstChild) {
                modalBody.removeChild(modalBody.firstChild);
            }

            if (rep.is_clean) {
                const cleanBox = document.createElement('div');
                cleanBox.className = 'clean-state-box';

                const icon = document.createElement('div');
                icon.className = 'clean-state-icon';
                icon.textContent = '✅';
                cleanBox.appendChild(icon);

                const title = document.createElement('h4');
                title.className = 'clean-state-title';
                title.textContent = 'No High-Risk Transactions Found';
                cleanBox.appendChild(title);

                const desc = document.createElement('p');
                desc.className = 'clean-state-desc';
                desc.textContent = `All accounts on ${dateStr} operated within normal parameters. No individuals breached the threshold (Frequency > 3 and Volume > $1,500 on ATM MCCs). No download is necessary.`;
                cleanBox.appendChild(desc);

                modalBody.appendChild(cleanBox);
            } else {
                const alerts = rep.alerts || [];
                const tableWrapper = document.createElement('div');
                tableWrapper.className = 'table-container';

                const table = document.createElement('table');
                table.className = 'table-human';

                const thead = document.createElement('thead');
                const headRow = document.createElement('tr');
                ['Account Number', 'Individual Name', 'Date', 'ATM Frequency', 'Total USD Vol', 'Alert Count'].forEach(h => {
                    const th = document.createElement('th');
                    th.textContent = h;
                    headRow.appendChild(th);
                });
                thead.appendChild(headRow);
                table.appendChild(thead);

                const tbody = document.createElement('tbody');
                alerts.forEach(a => {
                    const tr = document.createElement('tr');

                    // Account
                    const tdAcct = document.createElement('td');
                    const code = document.createElement('code');
                    code.textContent = a.account_number || '';
                    tdAcct.appendChild(code);
                    tr.appendChild(tdAcct);

                    // Name
                    const tdName = document.createElement('td');
                    tdName.textContent = a.individual_name || 'N/A';
                    tr.appendChild(tdName);

                    // Date
                    const tdDate = document.createElement('td');
                    tdDate.textContent = a.alert_date || dateStr;
                    tr.appendChild(tdDate);

                    // Frequency
                    const tdFreq = document.createElement('td');
                    const freqBadge = document.createElement('span');
                    freqBadge.className = 'badge badge-warning';
                    freqBadge.textContent = `${a.transaction_frequency || 0} Tx`;
                    tdFreq.appendChild(freqBadge);
                    tr.appendChild(tdFreq);

                    // Total USD
                    const tdUsd = document.createElement('td');
                    tdUsd.textContent = `$${Number(a.total_usd_equivalent || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                    tr.appendChild(tdUsd);

                    // Alert Count
                    const tdAlertCount = document.createElement('td');
                    const alertBadge = document.createElement('span');
                    alertBadge.className = 'badge badge-danger';
                    alertBadge.textContent = `+${a.alert_count || 1} Alert`;
                    tdAlertCount.appendChild(alertBadge);
                    tr.appendChild(tdAlertCount);

                    tbody.appendChild(tr);
                });
                table.appendChild(tbody);
                tableWrapper.appendChild(table);
                modalBody.appendChild(tableWrapper);
            }
        }

        if (reportModal) {
            reportModal.classList.remove('hidden');
        }
    }

    // --- Render Cumulative Watchlist ---
    function renderCumulativeWatchlist() {
        if (!cumulativeWatchlistTbody) return;

        while (cumulativeWatchlistTbody.firstChild) {
            cumulativeWatchlistTbody.removeChild(cumulativeWatchlistTbody.firstChild);
        }

        const summary = (overviewData && overviewData.ledger_summary) || {};
        const accounts = summary.top_flagged_accounts || [];
        const threshold = (overviewData && overviewData.cumulative_threshold) || 3;

        let filtered = [];
        if (currentWatchlistFilter === 'breached') {
            filtered = accounts.filter(acc => (acc.cumulative_alerts || 0) >= threshold);
        } else if (currentWatchlistFilter === 'emerging') {
            filtered = accounts.filter(acc => (acc.cumulative_alerts || 0) < threshold);
        } else {
            filtered = accounts;
        }

        if (filtered.length === 0) {
            const tr = document.createElement('tr');
            const td = document.createElement('td');
            td.colSpan = 7;
            td.className = 'hub-table-empty';
            td.textContent = currentWatchlistFilter === 'breached'
                ? 'No accounts currently meet or exceed the 3-day cumulative alert threshold.'
                : 'No tracked accounts found for this filter.';
            tr.appendChild(td);
            cumulativeWatchlistTbody.appendChild(tr);
            return;
        }

        filtered.forEach(acc => {
            const tr = document.createElement('tr');

            // Card
            const tdCard = document.createElement('td');
            tdCard.textContent = (acc.card_key || '').toUpperCase();
            tr.appendChild(tdCard);

            // Account
            const tdAcct = document.createElement('td');
            const code = document.createElement('code');
            code.textContent = acc.account_number || '';
            tdAcct.appendChild(code);
            tr.appendChild(tdAcct);

            // Name
            const tdName = document.createElement('td');
            tdName.textContent = acc.individual_name || 'N/A';
            tr.appendChild(tdName);

            // Accumulated Alerts
            const tdAlerts = document.createElement('td');
            const badge = document.createElement('span');
            const count = acc.cumulative_alerts || 0;
            badge.className = count >= threshold ? 'badge badge-danger' : 'badge badge-warning';
            badge.textContent = `+${count} Alerts`;
            tdAlerts.appendChild(badge);
            tr.appendChild(tdAlerts);

            // Flagged Dates
            const tdDates = document.createElement('td');
            tdDates.textContent = (acc.flagged_dates || []).join(', ');
            tr.appendChild(tdDates);

            // Last Flagged
            const tdLast = document.createElement('td');
            tdLast.textContent = acc.last_flagged_date || '';
            tr.appendChild(tdLast);

            // Action
            const tdAction = document.createElement('td');
            if (acc.cumulative_report_file) {
                const a = document.createElement('a');
                a.className = 'btn btn-primary btn-sm';
                a.textContent = '📥 Full History Dossier (.xlsx)';
                a.href = `/api/task1/automated/download/cumulative/${encodeURIComponent(acc.cumulative_report_file)}`;
                a.setAttribute('download', acc.cumulative_report_file);
                tdAction.appendChild(a);
            } else {
                const span = document.createElement('span');
                span.className = 'badge badge-muted';
                span.textContent = `Under Threshold (< ${threshold})`;
                tdAction.appendChild(span);
            }
            tr.appendChild(tdAction);

            cumulativeWatchlistTbody.appendChild(tr);
        });
    }

    // --- Render Daily Reports Archive ---
    function renderDailyArchive() {
        if (!dailyArchiveTbody) return;

        while (dailyArchiveTbody.firstChild) {
            dailyArchiveTbody.removeChild(dailyArchiveTbody.firstChild);
        }

        const reports = (overviewData && overviewData.recent_daily_reports) || [];
        let filtered = reports;
        if (currentArchiveCardFilter !== 'all') {
            filtered = reports.filter(r => (r.card || '').toUpperCase() === currentArchiveCardFilter.toUpperCase());
        }

        if (filtered.length === 0) {
            const tr = document.createElement('tr');
            const td = document.createElement('td');
            td.colSpan = 7;
            td.className = 'hub-table-empty';
            td.textContent = 'No generated daily reports found matching filter.';
            tr.appendChild(td);
            dailyArchiveTbody.appendChild(tr);
            return;
        }

        filtered.forEach(rep => {
            const tr = document.createElement('tr');

            // Card
            const tdCard = document.createElement('td');
            tdCard.textContent = rep.card || 'VISA';
            tr.appendChild(tdCard);

            // Date
            const tdDate = document.createElement('td');
            tdDate.textContent = rep.date || '';
            tr.appendChild(tdDate);

            // Status & Flagged Count
            const tdStatus = document.createElement('td');
            const badge = document.createElement('span');
            if (rep.is_clean) {
                badge.className = 'badge badge-success';
                badge.textContent = '✓ Clean Day (0 Flagged)';
            } else {
                badge.className = 'badge badge-danger';
                badge.textContent = `⚠️ ${rep.flagged_transactions_count} Flagged Tx (${rep.flagged_individuals_count} Indiv)`;
            }
            tdStatus.appendChild(badge);
            tr.appendChild(tdStatus);

            // Total Volume
            const tdVol = document.createElement('td');
            tdVol.textContent = `$${Number(rep.total_usd_volume || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            tr.appendChild(tdVol);

            // File Size
            const tdSize = document.createElement('td');
            tdSize.textContent = formatBytes(rep.size_bytes);
            tr.appendChild(tdSize);

            // Generated At
            const tdTime = document.createElement('td');
            tdTime.textContent = rep.generated_at || rep.modified_at || '';
            tr.appendChild(tdTime);

            // Actions: View & Download
            const tdAction = document.createElement('td');
            const actionGroup = document.createElement('div');
            actionGroup.className = 'hub-downloads-group';

            const btnView = document.createElement('button');
            btnView.type = 'button';
            btnView.className = 'btn btn-outline btn-sm';
            btnView.textContent = '🔍 View';
            btnView.addEventListener('click', () => {
                openModalForReport(rep);
            });
            actionGroup.appendChild(btnView);

            const btnDown = document.createElement('a');
            btnDown.className = 'btn btn-sm ' + (rep.is_clean ? 'btn-outline' : 'btn-primary');
            btnDown.textContent = rep.is_clean ? '⬇ Empty (.xlsx)' : '⬇ Download';
            btnDown.href = `/api/task1/automated/download/daily/${encodeURIComponent(rep.filename)}`;
            btnDown.setAttribute('download', rep.filename);
            actionGroup.appendChild(btnDown);

            tdAction.appendChild(actionGroup);
            tr.appendChild(tdAction);

            dailyArchiveTbody.appendChild(tr);
        });
    }

    // --- Load Overview Data ---
    async function loadReportsHubData() {
        try {
            const resp = await fetch('/api/task1/automated/overview');
            if (!resp.ok) return;
            const data = await resp.json();
            overviewData = data;

            if (hubSimDate && !hubSimDate.value && data.yesterday_date) {
                hubSimDate.value = data.yesterday_date;
            }

            renderCumulativeWatchlist();
            renderDailyArchive();
        } catch (e) {
            console.warn('Failed to load reports overview:', e);
        }
    }

    // Watchlist Filter Tab handlers
    function setupWatchlistFilters() {
        const filters = [
            { el: filterBreached, mode: 'breached' },
            { el: filterEmerging, mode: 'emerging' },
            { el: filterAll, mode: 'all' },
        ];

        filters.forEach(({ el, mode }) => {
            if (!el) return;
            el.addEventListener('click', () => {
                currentWatchlistFilter = mode;
                filters.forEach(f => {
                    if (f.el) {
                        f.el.classList.toggle('active', f.mode === mode);
                        f.el.setAttribute('aria-selected', f.mode === mode ? 'true' : 'false');
                    }
                });
                renderCumulativeWatchlist();
            });
        });
    }

    // Archive Card Filter handler
    if (archiveCardFilter) {
        archiveCardFilter.addEventListener('change', () => {
            currentArchiveCardFilter = archiveCardFilter.value;
            renderDailyArchive();
        });
    }

    if (btnRefreshArchive) {
        btnRefreshArchive.addEventListener('click', () => {
            loadReportsHubData();
        });
    }

    // Batch Runner Handler
    if (hubBtnRunBatch) {
        hubBtnRunBatch.addEventListener('click', async () => {
            const dateVal = hubSimDate ? hubSimDate.value.trim() : '';
            if (!dateVal) {
                showNotification('error', 'Please select a date to simulate batch run.');
                return;
            }

            const cardChoice = hubSimCard ? hubSimCard.value : 'all';
            const cardsPayload = cardChoice === 'all' ? ['visa', 'pinelabs', 'vegapay'] : [cardChoice];

            if (hubBatchSpinner) hubBatchSpinner.classList.remove('hidden');
            hubBtnRunBatch.disabled = true;

            try {
                const resp = await fetch('/api/task1/automated/run-batch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ target_date: dateVal, cards: cardsPayload })
                });

                if (!resp.ok) {
                    const err = await resp.json();
                    throw new Error(err.detail || 'Batch execution failed');
                }

                const res = await resp.json();
                showNotification(
                    'success',
                    `Batch executed for ${dateVal}! Flagged Individuals: ${res.total_flagged_individuals}, Cumulative Dossiers Generated: ${res.total_cumulative_reports}`
                );
                await loadReportsHubData();

            } catch (err) {
                showNotification('error', 'Batch simulation error: ' + err.message);
            } finally {
                if (hubBatchSpinner) hubBatchSpinner.classList.add('hidden');
                hubBtnRunBatch.disabled = false;
            }
        });
    }

    // Initialize on DOM ready
    window.addEventListener('DOMContentLoaded', () => {
        setupWatchlistFilters();
        loadReportsHubData();
        window.CardLyze.initSession().catch(err => {
            showNotification('error', 'Could not initialize session: ' + err.message);
        });
    });

})(window, document);

