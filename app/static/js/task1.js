/**
 * Task 1: TMS-ATM High-Risk Transaction Monitoring Frontend Controller.
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
    let currentCard = 'visa';
    let availableDates = [];
    let isProcessing = false;
    let cachedResults = null;
    let selectedIndividualAccount = null;

    // Card Date Info Defaults
    const CARD_DATE_INFO = {
        visa: {
            column_name: 'spdate',
            column_label: 'Transaction Date (spdate)',
            format: 'DDMMYYYY',
            description: 'Cardholder transaction date (spdate). Daily batch extracts group records by actual transaction date.'
        },
        pinelabs: {
            column_name: 'Transaction Date',
            column_label: 'Transaction Date',
            format: 'DD/MM/YYYY HH:MM:SS',
            description: 'Cardholder transaction timestamp. Daily batch extracts group records by transaction date.'
        },
        vegapay: {
            column_name: 'Transaction Date',
            column_label: 'Transaction Date',
            format: 'DD-MM-YYYY',
            description: 'Cardholder transaction date. Daily batch extracts group records by transaction date.'
        }
    };

    // DOM Elements
    const cardOptions = document.querySelectorAll('.card-option');
    const uploadDropzone = document.getElementById('upload-dropzone');
    const fileInput = document.getElementById('file-input');
    const btnLoadSample = document.getElementById('btn-load-sample');
    const loadedFileIndicator = document.getElementById('loaded-file-indicator');

    const step2Section = document.getElementById('step-2-detection-section');
    const selectTargetDate = document.getElementById('select-target-date');
    const btnRunDetection = document.getElementById('btn-run-detection');
    const dateColName = document.getElementById('date-col-name');
    const dateColNote = document.getElementById('date-col-note');

    const loadingContainer = document.getElementById('loading-container');
    const loadingTitle = document.getElementById('loading-title');
    const loadingDesc = document.getElementById('loading-desc');

    const step3ResultsSection = document.getElementById('step-3-results-section');
    const kpiTargetDate = document.getElementById('kpi-target-date');
    const kpiDateColLabel = document.getElementById('kpi-date-col-label');
    const kpiTotalAtm = document.getElementById('kpi-total-atm');
    const kpiFlaggedCount = document.getElementById('kpi-flagged-count');
    const kpiFlaggedRows = document.getElementById('kpi-flagged-rows');

    const alertTableDateCol = document.getElementById('alert-table-date-col');
    const alertsSummaryTbody = document.getElementById('alerts-summary-tbody');

    const individualFilterBanner = document.getElementById('individual-filter-banner');
    const filterIndividualName = document.getElementById('filter-individual-name');
    const filterIndividualStats = document.getElementById('filter-individual-stats');
    const btnResetIndividualFilter = document.getElementById('btn-reset-individual-filter');

    const flaggedTitle = document.getElementById('flagged-transactions-title');
    const flaggedSubtitle = document.getElementById('flagged-transactions-subtitle');
    const flaggedThead = document.getElementById('flagged-table-thead');
    const flaggedTbody = document.getElementById('flagged-table-tbody');

    const btnDownloadFlaggedCsv = document.getElementById('btn-download-flagged-csv');
    const btnDownloadFlaggedExcel = document.getElementById('btn-download-flagged-excel');
    const btnExportAlertsCsv = document.getElementById('btn-export-alerts-csv');

    const notificationBanner = document.getElementById('notification-banner');
    const notificationMessage = document.getElementById('notification-message');
    const notificationIcon = document.getElementById('notification-icon');
    const notificationDismiss = document.getElementById('notification-dismiss');

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

    function hideNotification() {
        if (!notificationBanner) return;
        notificationBanner.className = 'notification-banner hidden';
        if (notificationMessage) {
            notificationMessage.textContent = '';
        }
    }

    if (notificationDismiss) {
        notificationDismiss.addEventListener('click', hideNotification);
    }

    // --- Loading State Helpers ---
    function showLoading(title, desc) {
        isProcessing = true;
        if (loadingTitle) loadingTitle.textContent = title || 'Processing...';
        if (loadingDesc) loadingDesc.textContent = desc || 'Please wait while records are processed in-memory.';
        if (loadingContainer) loadingContainer.classList.remove('hidden');
    }

    function hideLoading() {
        isProcessing = false;
        if (loadingContainer) loadingContainer.classList.add('hidden');
    }

    // --- Update Date Column Info in UI ---
    function updateDateInfo(info) {
        const dateMeta = info || CARD_DATE_INFO[currentCard] || {
            column_name: 'Date',
            column_label: 'Transaction Date',
            description: 'Filtering records by cardholder transaction date.'
        };

        if (dateColName) dateColName.textContent = dateMeta.column_label || dateMeta.column_name;
        if (dateColNote) dateColNote.textContent = dateMeta.description || '';
        if (kpiDateColLabel) kpiDateColLabel.textContent = dateMeta.column_name || 'Transaction Date';
        if (alertTableDateCol) alertTableDateCol.textContent = dateMeta.column_name || 'Transaction Date';
    }

    // --- Card Option Selection ---
    function selectCard(cardKey) {
        currentCard = cardKey.toLowerCase();
        selectedIndividualAccount = null;
        cachedResults = null;

        cardOptions.forEach(opt => {
            const isMatch = opt.getAttribute('data-card') === currentCard;
            if (isMatch) {
                opt.classList.add('selected');
                opt.setAttribute('aria-checked', 'true');
            } else {
                opt.classList.remove('selected');
                opt.setAttribute('aria-checked', 'false');
            }
        });

        updateDateInfo(CARD_DATE_INFO[currentCard]);

        // Reset steps 2 and 3 when switching card
        if (step2Section) step2Section.classList.add('hidden');
        if (step3ResultsSection) step3ResultsSection.classList.add('hidden');
        if (loadedFileIndicator) {
            loadedFileIndicator.textContent = 'Selected card: ' + currentCard.toUpperCase() + '. Load sample or upload file.';
        }
    }

    cardOptions.forEach(opt => {
        opt.addEventListener('click', () => {
            const key = opt.getAttribute('data-card');
            if (key) selectCard(key);
        });
        opt.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                const key = opt.getAttribute('data-card');
                if (key) selectCard(key);
            }
        });
    });

    // --- Populate Dates Dropdown ---
    function populateDates(dates, defaultDate) {
        availableDates = dates || [];
        while (selectTargetDate.firstChild) {
            selectTargetDate.removeChild(selectTargetDate.firstChild);
        }

        if (availableDates.length === 0) {
            const opt = document.createElement('option');
            opt.value = '';
            opt.textContent = 'No dates found in file';
            selectTargetDate.appendChild(opt);
            return;
        }

        availableDates.forEach(dateStr => {
            const opt = document.createElement('option');
            opt.value = dateStr;
            opt.textContent = dateStr;
            if (defaultDate && dateStr === defaultDate) {
                opt.selected = true;
            }
            selectTargetDate.appendChild(opt);
        });

        if (step2Section) step2Section.classList.remove('hidden');
    }

    // --- Load Bundled Sample File ---
    async function loadSampleFile() {
        if (isProcessing) return;
        hideNotification();
        showLoading('Loading Local Sample Dataset', 'Reading ' + currentCard.toUpperCase() + ' transaction data into memory...');

        try {
            const res = await window.CardLyze.fetchWithSession('/api/task1/' + currentCard + '/load-sample', {
                method: 'POST'
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || 'Failed to load sample dataset (HTTP ' + res.status + ')');
            }

            const data = await res.json();
            if (loadedFileIndicator) {
                loadedFileIndicator.textContent = 'Loaded: ' + data.filename + ' (' + data.total_rows.toLocaleString() + ' rows, ' + data.total_columns + ' columns)';
            }

            updateDateInfo(data.date_info);
            populateDates(data.available_dates, data.default_date);
            showNotification('success', 'Loaded sample ' + data.filename + ' successfully. Please choose a target date.');
        } catch (err) {
            showNotification('error', err.message);
        } finally {
            hideLoading();
        }
    }

    if (btnLoadSample) {
        btnLoadSample.addEventListener('click', loadSampleFile);
    }

    // --- File Upload Handling ---
    if (uploadDropzone && fileInput) {
        uploadDropzone.addEventListener('click', () => fileInput.click());
        uploadDropzone.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                fileInput.click();
            }
        });

        uploadDropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadDropzone.classList.add('drag-active');
        });

        uploadDropzone.addEventListener('dragleave', () => {
            uploadDropzone.classList.remove('drag-active');
        });

        uploadDropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadDropzone.classList.remove('drag-active');
            if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                handleFileUpload(e.dataTransfer.files[0]);
            }
        });

        fileInput.addEventListener('change', () => {
            if (fileInput.files && fileInput.files.length > 0) {
                handleFileUpload(fileInput.files[0]);
            }
        });
    }

    async function handleFileUpload(file) {
        if (!file) return;
        if (!file.name.toLowerCase().endsWith('.xlsx')) {
            showNotification('error', 'Only Excel workbooks (.xlsx) are supported.');
            return;
        }

        hideNotification();
        showLoading('Uploading & Ingesting File', 'Reading workbook bytes into in-memory DataFrame...');

        try {
            const session = await window.CardLyze.initSession();
            const res = await fetch('/api/task1/' + currentCard + '/upload', {
                method: 'POST',
                headers: {
                    'X-Session-Id': session,
                    'X-Filename': file.name
                },
                body: file
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || 'Upload failed (HTTP ' + res.status + ')');
            }

            const data = await res.json();
            if (loadedFileIndicator) {
                loadedFileIndicator.textContent = 'Uploaded: ' + data.filename + ' (' + data.total_rows.toLocaleString() + ' rows, ' + data.total_columns + ' columns)';
            }

            updateDateInfo(data.date_info);
            populateDates(data.available_dates, data.default_date);
            showNotification('success', 'File ' + data.filename + ' ingested. Select a date to run detection.');
        } catch (err) {
            showNotification('error', err.message);
        } finally {
            hideLoading();
            if (fileInput) fileInput.value = '';
        }
    }

    // --- Run Task 1 Detection ---
    async function runDetection() {
        const targetDate = selectTargetDate ? selectTargetDate.value : '';
        if (!targetDate) {
            showNotification('warning', 'Please select a target monitoring date.');
            return;
        }

        selectedIndividualAccount = null;
        hideNotification();
        showLoading('Running TMS-ATM Detection', 'Filtering ATM MCCs (6011, 6010, 6050, 6051) and evaluating frequency > 3 & USD volume > $1500 on ' + targetDate + '...');

        try {
            const res = await window.CardLyze.fetchWithSession('/api/task1/' + currentCard + '/detect', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    target_date: targetDate
                })
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || 'Detection failed (HTTP ' + res.status + ')');
            }

            const data = await res.json();
            cachedResults = data;
            renderResults(data);
            showNotification('success', 'Detection complete for ' + targetDate + ': found ' + data.flagged_individuals_count + ' flagged individual(s).');
        } catch (err) {
            showNotification('error', err.message);
        } finally {
            hideLoading();
        }
    }

    if (btnRunDetection) {
        btnRunDetection.addEventListener('click', runDetection);
    }

    // --- Export Trigger Helper ---
    async function triggerBlobDownload(url, fallbackFilename) {
        if (isProcessing) return;
        hideNotification();
        showLoading('Generating Export', 'Preparing in-memory download...');

        try {
            const res = await window.CardLyze.fetchWithSession(url, {
                method: 'GET'
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || 'Export failed (HTTP ' + res.status + ')');
            }

            const disposition = res.headers.get('Content-Disposition') || '';
            let filename = fallbackFilename;
            const match = disposition.match(/filename=["']?([^"';]+)["']?/i);
            if (match && match[1]) {
                filename = match[1].trim();
            }

            const blob = await res.blob();
            const blobUrl = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = blobUrl;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);

            showNotification('success', 'Downloaded ' + filename + ' successfully.');
        } catch (err) {
            showNotification('error', err.message);
        } finally {
            hideLoading();
        }
    }

    // --- Individual View & Export Handlers ---
    function filterTransactionsByIndividual(acctNumber, individualName, statsText) {
        selectedIndividualAccount = acctNumber;

        // Highlight selected row in summary table
        const allTrs = alertsSummaryTbody.querySelectorAll('.task1-tr');
        allTrs.forEach(tr => {
            if (tr.getAttribute('data-acct') === acctNumber) {
                tr.classList.add('selected-individual');
            } else {
                tr.classList.remove('selected-individual');
            }
        });

        // Show individual filter banner
        if (individualFilterBanner) {
            individualFilterBanner.classList.remove('hidden');
        }
        if (filterIndividualName) {
            filterIndividualName.textContent = individualName || acctNumber;
        }
        if (filterIndividualStats) {
            filterIndividualStats.textContent = ' (' + statsText + ')';
        }

        // Update titles and export buttons
        if (flaggedTitle) {
            flaggedTitle.textContent = 'Transactions for ' + (individualName || acctNumber);
        }
        if (flaggedSubtitle) {
            flaggedSubtitle.textContent = 'Showing only raw records for account ' + acctNumber + ' (' + statsText + ')';
        }
        if (btnDownloadFlaggedCsv) {
            btnDownloadFlaggedCsv.textContent = '📥 Download Individual CSV';
        }
        if (btnDownloadFlaggedExcel) {
            btnDownloadFlaggedExcel.textContent = '📥 Download Individual Excel';
        }

        // Re-render transactions table with filtered rows
        renderFlaggedTransactionsTable();
    }

    function resetIndividualFilter() {
        selectedIndividualAccount = null;

        // Remove highlights
        const allTrs = alertsSummaryTbody.querySelectorAll('.task1-tr');
        allTrs.forEach(tr => tr.classList.remove('selected-individual'));

        // Hide banner
        if (individualFilterBanner) {
            individualFilterBanner.classList.add('hidden');
        }

        // Reset titles and export buttons
        if (flaggedTitle) {
            flaggedTitle.textContent = 'Flagged Unmodified Transactions';
        }
        if (flaggedSubtitle) {
            flaggedSubtitle.textContent = 'Exact raw source records for flagged individuals (zero modifications, zero added columns).';
        }
        if (btnDownloadFlaggedCsv) {
            btnDownloadFlaggedCsv.textContent = '📥 Download Flagged (CSV)';
        }
        if (btnDownloadFlaggedExcel) {
            btnDownloadFlaggedExcel.textContent = '📥 Download Flagged (Excel)';
        }

        // Re-render transactions table with all rows
        renderFlaggedTransactionsTable();
    }

    if (btnResetIndividualFilter) {
        btnResetIndividualFilter.addEventListener('click', resetIndividualFilter);
    }

    // --- Render Results & Tables ---
    function renderResults(data) {
        if (!step3ResultsSection) return;
        step3ResultsSection.classList.remove('hidden');

        updateDateInfo(data.date_info);

        // Update KPIs
        if (kpiTargetDate) kpiTargetDate.textContent = data.target_date || '-';
        if (kpiTotalAtm) kpiTotalAtm.textContent = (data.total_atm_transactions || 0).toLocaleString();
        if (kpiFlaggedCount) kpiFlaggedCount.textContent = (data.flagged_individuals_count || 0).toLocaleString();
        if (kpiFlaggedRows) kpiFlaggedRows.textContent = (data.total_flagged_transactions || 0).toLocaleString();

        // 1. Render Alerts Summary Table
        while (alertsSummaryTbody.firstChild) {
            alertsSummaryTbody.removeChild(alertsSummaryTbody.firstChild);
        }

        const alerts = data.alerts || [];
        if (alerts.length === 0) {
            const tr = document.createElement('tr');
            tr.className = 'task1-tr';
            const td = document.createElement('td');
            td.colSpan = 7;
            td.className = 'task1-td empty-state-cell';
            td.textContent = 'No individuals exceeded the threshold (frequency > 3 and total USD > $1500) on ' + data.target_date + '.';
            tr.appendChild(td);
            alertsSummaryTbody.appendChild(tr);
        } else {
            alerts.forEach(item => {
                const tr = document.createElement('tr');
                tr.className = 'task1-tr';
                tr.setAttribute('data-acct', item.account_number || '');

                const acct = item.account_number || '';
                const name = item.individual_name || '-';
                const freq = item.transaction_frequency || 0;
                const usd = item.total_usd_equivalent || 0;
                const statsStr = freq + ' txns • $' + Number(usd).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' USD';

                // Column 1: Individual Actions & Export
                const tdActions = document.createElement('td');
                tdActions.className = 'task1-td';
                const actionsWrapper = document.createElement('div');
                actionsWrapper.className = 'task1-actions-cell';

                // View button
                const btnView = document.createElement('button');
                btnView.type = 'button';
                btnView.className = 'btn-action-sm';
                btnView.textContent = '👁️ View';
                btnView.title = 'Filter transactions table to this individual';
                btnView.addEventListener('click', () => {
                    filterTransactionsByIndividual(acct, name, statsStr);
                });

                // Individual CSV Export button
                const btnCsv = document.createElement('button');
                btnCsv.type = 'button';
                btnCsv.className = 'btn-action-sm btn-action-csv';
                btnCsv.textContent = '📥 CSV';
                btnCsv.title = 'Download CSV report for ' + name;
                btnCsv.addEventListener('click', () => {
                    triggerBlobDownload(
                        '/api/task1/export-csv?account_number=' + encodeURIComponent(acct),
                        currentCard + '_tms_atm_' + acct + '_' + item.alert_date + '.csv'
                    );
                });

                // Individual Excel Export button
                const btnExcel = document.createElement('button');
                btnExcel.type = 'button';
                btnExcel.className = 'btn-action-sm btn-action-excel';
                btnExcel.textContent = '📥 Excel';
                btnExcel.title = 'Download Excel report for ' + name;
                btnExcel.addEventListener('click', () => {
                    triggerBlobDownload(
                        '/api/task1/export-excel?account_number=' + encodeURIComponent(acct),
                        currentCard + '_tms_atm_' + acct + '_' + item.alert_date + '.xlsx'
                    );
                });

                actionsWrapper.appendChild(btnView);
                actionsWrapper.appendChild(btnCsv);
                actionsWrapper.appendChild(btnExcel);
                tdActions.appendChild(actionsWrapper);
                tr.appendChild(tdActions);

                // Column 2: Alert badge
                const tdAlert = document.createElement('td');
                tdAlert.className = 'task1-td';
                const badge = document.createElement('span');
                badge.className = 'task1-alert-tag';
                badge.textContent = '+1 Alert';
                tdAlert.appendChild(badge);
                tr.appendChild(tdAlert);

                // Column 3: Date
                const tdDate = document.createElement('td');
                tdDate.className = 'task1-td';
                tdDate.textContent = item.alert_date || '';
                tr.appendChild(tdDate);

                // Column 4: Account Number
                const tdAcct = document.createElement('td');
                tdAcct.className = 'task1-td';
                tdAcct.textContent = acct;
                tr.appendChild(tdAcct);

                // Column 5: Individual Name / PAN
                const tdName = document.createElement('td');
                tdName.className = 'task1-td';
                tdName.textContent = name;
                tr.appendChild(tdName);

                // Column 6: Frequency (> 3)
                const tdFreq = document.createElement('td');
                tdFreq.className = 'task1-td';
                tdFreq.textContent = String(freq);
                tr.appendChild(tdFreq);

                // Column 7: Total USD Equivalent (> $1500)
                const tdUsd = document.createElement('td');
                tdUsd.className = 'task1-td';
                tdUsd.textContent = '$' + Number(usd).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                tr.appendChild(tdUsd);

                alertsSummaryTbody.appendChild(tr);
            });
        }

        // Render transactions table
        renderFlaggedTransactionsTable();

        // Scroll to results smoothly
        step3ResultsSection.scrollIntoView({ behavior: 'smooth' });
    }

    // --- Render Flagged Transactions Table ---
    function renderFlaggedTransactionsTable() {
        if (!cachedResults) return;

        while (flaggedThead.firstChild) {
            flaggedThead.removeChild(flaggedThead.firstChild);
        }
        while (flaggedTbody.firstChild) {
            flaggedTbody.removeChild(flaggedTbody.firstChild);
        }

        const columns = cachedResults.columns || [];
        let previewRows = cachedResults.preview_rows || [];

        // If an individual account is selected, filter rows to that account
        if (selectedIndividualAccount) {
            // Find account column in records
            previewRows = previewRows.filter(row => {
                const val = row.spacct || row['Wallet Number'] || row['Account Number'] || row['Customer ID'] || '';
                return String(val).trim() === String(selectedIndividualAccount).trim();
            });
        }

        // Header Row
        const trHead = document.createElement('tr');
        trHead.className = 'task1-tr';
        columns.forEach(colName => {
            const th = document.createElement('th');
            th.className = 'task1-th';
            th.textContent = colName;
            trHead.appendChild(th);
        });
        flaggedThead.appendChild(trHead);

        // Body Rows
        if (previewRows.length === 0) {
            const tr = document.createElement('tr');
            tr.className = 'task1-tr';
            const td = document.createElement('td');
            td.colSpan = Math.max(1, columns.length);
            td.className = 'task1-td empty-state-cell';
            td.textContent = selectedIndividualAccount ?
                'No transactions found for this individual in the preview set.' :
                'No transactions to display.';
            tr.appendChild(td);
            flaggedTbody.appendChild(tr);
        } else {
            previewRows.forEach(row => {
                const tr = document.createElement('tr');
                tr.className = 'task1-tr';
                columns.forEach(colName => {
                    const td = document.createElement('td');
                    td.className = 'task1-td';
                    const val = row[colName];
                    td.textContent = (val === null || val === undefined) ? '' : String(val);
                    tr.appendChild(td);
                });
                flaggedTbody.appendChild(tr);
            });
        }
    }

    // --- Global Export Buttons ---
    if (btnDownloadFlaggedCsv) {
        btnDownloadFlaggedCsv.addEventListener('click', () => {
            let url = '/api/task1/export-csv';
            let filename = currentCard + '_tms_atm_flagged.csv';
            if (selectedIndividualAccount) {
                url += '?account_number=' + encodeURIComponent(selectedIndividualAccount);
                filename = currentCard + '_tms_atm_' + selectedIndividualAccount + '.csv';
            }
            triggerBlobDownload(url, filename);
        });
    }

    if (btnDownloadFlaggedExcel) {
        btnDownloadFlaggedExcel.addEventListener('click', () => {
            let url = '/api/task1/export-excel';
            let filename = currentCard + '_tms_atm_flagged.xlsx';
            if (selectedIndividualAccount) {
                url += '?account_number=' + encodeURIComponent(selectedIndividualAccount);
                filename = currentCard + '_tms_atm_' + selectedIndividualAccount + '.xlsx';
            }
            triggerBlobDownload(url, filename);
        });
    }

    if (btnExportAlertsCsv) {
        btnExportAlertsCsv.addEventListener('click', () => {
            triggerBlobDownload('/api/task1/export-alerts-csv', currentCard + '_tms_atm_alerts.csv');
        });
    }

    // =========================================================================
    // TMS Executive Dashboard Controller & On-Top Modal Manager
    // Strict CSP: Pure DOM methods, zero innerHTML, zero inline styles
    // =========================================================================

    const hubYesterdayDate = document.getElementById('hub-yesterday-date');
    const hubYesterdayStatus = document.getElementById('hub-yesterday-status');
    const hubTotalFlaggedTx = document.getElementById('hub-total-flagged-tx');
    const hubTotalFlaggedIndiv = document.getElementById('hub-total-flagged-indiv');
    const hubCumulativeCount = document.getElementById('hub-cumulative-count');
    const hubMonthlyLabel = document.getElementById('hub-monthly-label');
    const hubMonthlyTx = document.getElementById('hub-monthly-tx');
    const hubMonthlySub = document.getElementById('hub-monthly-sub');

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
    let globalOverviewData = null;

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

    function openModalForCard(cardKey) {
        if (!globalOverviewData || !globalOverviewData.yesterday_status) return;
        const st = globalOverviewData.yesterday_status[cardKey];
        if (!st) return;

        const cardUpper = cardKey.toUpperCase();
        const dateStr = globalOverviewData.yesterday_date || '--';

        if (modalTitle) {
            modalTitle.textContent = `${cardUpper} - Yesterday's Report Details (${dateStr})`;
        }

        if (modalSubtitle) {
            modalSubtitle.textContent = st.is_clean
                ? 'Status: Clean Day (0 Flagged Transactions)'
                : `${st.flagged_transactions_count} Flagged Transactions | ${st.flagged_individuals_count} Individual(s) | USD $${Number(st.total_usd_volume || 0).toLocaleString()}`;
        }

        if (btnModalDownload) {
            if (!st.is_clean && st.generated) {
                btnModalDownload.classList.remove('hidden');
                currentModalDownloadUrl = `/api/task1/automated/download/daily/${encodeURIComponent(st.expected_file)}`;
                currentModalDownloadFilename = st.expected_file;
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

            if (st.is_clean) {
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
                // Table of Flagged Alerts
                const alerts = st.alerts || [];
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

    // 3-Card Tab Switcher setup
    const cardTabs = ['visa', 'pinelabs', 'vegapay'];
    cardTabs.forEach(c => {
        const tabBtn = document.getElementById(`tab-${c}`);
        if (tabBtn) {
            tabBtn.addEventListener('click', () => {
                cardTabs.forEach(other => {
                    const btn = document.getElementById(`tab-${other}`);
                    const panel = document.getElementById(`panel-${other}`);
                    if (btn) {
                        btn.classList.toggle('active', other === c);
                        btn.setAttribute('aria-selected', other === c ? 'true' : 'false');
                    }
                    if (panel) {
                        panel.classList.toggle('hidden', other !== c);
                    }
                });
            });
        }

        // View button in provider panel
        const viewBtn = document.getElementById(`btn-view-${c}`);
        if (viewBtn) {
            viewBtn.addEventListener('click', () => {
                openModalForCard(c);
            });
        }

        // Download button in provider panel
        const downBtn = document.getElementById(`btn-download-${c}`);
        if (downBtn) {
            downBtn.addEventListener('click', () => {
                if (!globalOverviewData || !globalOverviewData.yesterday_status) return;
                const st = globalOverviewData.yesterday_status[c];
                if (st && st.generated) {
                    if (st.is_clean) {
                        showNotification('info', `Report for ${c.toUpperCase()} on ${globalOverviewData.yesterday_date} is clean (0 Flagged). Downloaded empty report.`);
                    }
                    const a = document.createElement('a');
                    a.href = `/api/task1/automated/download/daily/${encodeURIComponent(st.expected_file)}`;
                    a.setAttribute('download', st.expected_file);
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                } else {
                    showNotification('error', `Report for ${c.toUpperCase()} has not been generated yet.`);
                }
            });
        }
    });

    async function loadAutomatedDashboard() {
        try {
            const resp = await fetch('/api/task1/automated/overview');
            if (!resp.ok) return;
            const data = await resp.json();
            globalOverviewData = data;

            // 1. Executive Top KPI Metrics
            if (hubYesterdayDate) hubYesterdayDate.textContent = data.yesterday_date || '--';

            const totals = data.yesterday_totals || {};
            if (hubTotalFlaggedTx) hubTotalFlaggedTx.textContent = totals.total_flagged_transactions || 0;
            if (hubTotalFlaggedIndiv) hubTotalFlaggedIndiv.textContent = totals.total_flagged_individuals || 0;

            const ledgerSummary = data.ledger_summary || {};
            if (hubCumulativeCount) {
                hubCumulativeCount.textContent = ledgerSummary.cumulative_breached_count || 0;
            }

            const monthly = data.monthly_summary || {};
            if (hubMonthlyLabel) {
                hubMonthlyLabel.textContent = `${monthly.current_month || 'Current Month'} Status`;
            }
            if (hubMonthlyTx) {
                hubMonthlyTx.textContent = `${monthly.flagged_transactions_count || 0} Tx`;
            }
            if (hubMonthlySub) {
                hubMonthlySub.textContent = monthly.historical_query_ready
                    ? 'Queried from AWS RDS'
                    : 'Awaiting Database Access';
            }

            // 2. Populate Each Card Provider Panel
            const yesterdayStatus = data.yesterday_status || {};
            cardTabs.forEach(c => {
                const st = yesterdayStatus[c];
                if (!st) return;

                const strip = document.getElementById(`strip-${c}`);
                const badge = document.getElementById(`badge-${c}`);
                const heading = document.getElementById(`heading-${c}`);
                const sub = document.getElementById(`sub-${c}`);
                const valTx = document.getElementById(`val-${c}-tx`);
                const valIndiv = document.getElementById(`val-${c}-indiv`);
                const valUsd = document.getElementById(`val-${c}-usd`);
                const valFile = document.getElementById(`val-${c}-file`);
                const downBtn = document.getElementById(`btn-download-${c}`);
                const hint = document.getElementById(`hint-${c}`);

                if (valTx) valTx.textContent = st.flagged_transactions_count || 0;
                if (valIndiv) valIndiv.textContent = st.flagged_individuals_count || 0;
                if (valUsd) {
                    valUsd.textContent = `$${Number(st.total_usd_volume || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
                }
                if (valFile) valFile.textContent = st.expected_file || '--';

                if (st.is_clean) {
                    if (strip) {
                        strip.className = 'provider-status-strip is-clean';
                    }
                    if (badge) {
                        badge.className = 'badge badge-success';
                        badge.textContent = '✓ Clean Day';
                    }
                    if (heading) {
                        heading.textContent = `0 Flagged Transactions for ${c.toUpperCase()}`;
                    }
                    if (sub) {
                        sub.textContent = `All accounts operated within standard thresholds on ${data.yesterday_date}.`;
                    }
                    if (downBtn) {
                        downBtn.className = 'btn btn-outline btn-sm';
                    }
                    if (hint) {
                        hint.textContent = '✓ Clean report (no high-risk transactions)';
                    }
                } else {
                    if (strip) {
                        strip.className = 'provider-status-strip has-alerts';
                    }
                    if (badge) {
                        badge.className = 'badge badge-danger';
                        badge.textContent = '⚠️ High-Risk Activity';
                    }
                    if (heading) {
                        heading.textContent = `${st.flagged_transactions_count} Flagged Transactions across ${st.flagged_individuals_count} Account(s)`;
                    }
                    if (sub) {
                        sub.textContent = `High-risk ATM pattern detected on ${data.yesterday_date}. Review details immediately.`;
                    }
                    if (downBtn) {
                        downBtn.className = 'btn btn-primary btn-sm';
                    }
                    if (hint) {
                        hint.textContent = '⚠️ Action required: Review flagged accounts';
                    }
                }
            });

        } catch (e) {
            console.warn('Failed to load executive dashboard overview:', e);
        }
    }

    // Initialize session and Dashboard on page load
    window.addEventListener('DOMContentLoaded', () => {
        updateDateInfo(CARD_DATE_INFO[currentCard]);
        loadAutomatedDashboard();
        window.CardLyze.initSession().catch(err => {
            showNotification('error', 'Could not initialize session: ' + err.message);
        });
    });

})(window, document);
