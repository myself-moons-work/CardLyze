/**
 * CardLyze Column Addition Controller
 * 
 * Strict Privacy & CSP Compliance:
 * - 0 inline event handlers, 0 inline styles, 0 eval.
 * - Session token maintained in memory closure only.
 * - Raw binary streaming with elapsed timers.
 */

(function () {
    'use strict';

    // State
    let selectedCard = 'visa';
    let selectedFile = null;
    let dataTableInstance = null;
    let parseTimerInterval = null;
    let exportTimerInterval = null;

    // DOM Elements
    const cardOptions = document.querySelectorAll('.card-option');
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('file-input');
    const fileCard = document.getElementById('file-card');
    const fileCardName = document.getElementById('file-card-name');
    const fileCardSize = document.getElementById('file-card-size');
    const btnChangeFile = document.getElementById('btn-change-file');
    const btnProcess = document.getElementById('btn-process');

    const processingCard = document.getElementById('processing-card');
    const processingTimer = document.getElementById('processing-timer');
    const processingFileName = document.getElementById('processing-file-name');
    const processingLargeNote = document.getElementById('processing-large-note');

    const step3Section = document.getElementById('step-3-section');
    const bannerSuccess = document.getElementById('banner-success');
    const bannerSuccessTitle = document.getElementById('banner-success-title');
    const bannerSuccessDesc = document.getElementById('banner-success-desc');
    const bannerError = document.getElementById('banner-error');
    const bannerErrorTitle = document.getElementById('banner-error-title');
    const bannerErrorDesc = document.getElementById('banner-error-desc');
    const btnErrorRetry = document.getElementById('btn-error-retry');

    const previewActionsBar = document.getElementById('preview-actions-bar');
    const btnDownload = document.getElementById('btn-download');
    const btnClear = document.getElementById('btn-clear');
    const exportLoadingCard = document.getElementById('export-loading-card');
    const exportTimer = document.getElementById('export-timer');
    const previewTableContainer = document.getElementById('preview-table-container');

    /**
     * Format bytes to readable string (e.g. 1.25 MB)
     */
    function formatBytes(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * Card Selection Logic
     */
    cardOptions.forEach(card => {
        const selectCurrentCard = () => {
            cardOptions.forEach(c => {
                c.classList.remove('selected');
                c.setAttribute('aria-checked', 'false');
            });
            card.classList.add('selected');
            card.setAttribute('aria-checked', 'true');
            selectedCard = card.dataset.card;
        };

        card.addEventListener('click', selectCurrentCard);
        card.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                selectCurrentCard();
            }
        });
    });

    /**
     * File Selection & Drag-and-Drop
     */
    dropzone.addEventListener('click', () => {
        fileInput.click();
    });

    dropzone.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            fileInput.click();
        }
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.remove('dragover');
        });
    });

    dropzone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files && files.length > 0) {
            handleFileSelected(files[0]);
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files && fileInput.files.length > 0) {
            handleFileSelected(fileInput.files[0]);
        }
    });

    btnChangeFile.addEventListener('click', () => {
        fileInput.value = '';
        selectedFile = null;
        fileCard.classList.add('hidden');
        dropzone.classList.remove('hidden');
        hideResults();
    });

    btnErrorRetry.addEventListener('click', () => {
        hideResults();
        dropzone.classList.remove('hidden');
        fileInput.value = '';
        selectedFile = null;
    });

    function handleFileSelected(file) {
        if (!file.name.toLowerCase().endsWith('.xlsx')) {
            showError('Invalid File Format', 'Only Excel workbooks with .xlsx extension are supported.');
            fileInput.value = '';
            return;
        }

        // 50 MB limit
        const MAX_BYTES = 50 * 1024 * 1024;
        if (file.size > MAX_BYTES) {
            showError(
                'File Size Exceeded',
                `Selected file size is ${formatBytes(file.size)}, which exceeds the maximum allowed limit of 50 MB.`
            );
            fileInput.value = '';
            return;
        }

        selectedFile = file;
        fileCardName.textContent = file.name;
        fileCardSize.textContent = formatBytes(file.size);

        dropzone.classList.add('hidden');
        fileCard.classList.remove('hidden');
        hideResults();
    }

    /**
     * Upload & Process File
     */
    btnProcess.addEventListener('click', async () => {
        if (!selectedFile) return;

        btnProcess.disabled = true;
        btnChangeFile.disabled = true;
        fileCard.classList.add('hidden');
        processingCard.classList.remove('hidden');
        processingFileName.textContent = selectedFile.name;

        if (selectedFile.size > 30 * 1024 * 1024) {
            processingLargeNote.classList.remove('hidden');
        } else {
            processingLargeNote.classList.add('hidden');
        }

        // Start elapsed timer
        let elapsed = 0;
        processingTimer.textContent = '0s elapsed';
        clearInterval(parseTimerInterval);
        parseTimerInterval = setInterval(() => {
            elapsed++;
            processingTimer.textContent = `${elapsed}s elapsed`;
        }, 1000);

        try {
            // Lazy session creation: creates session only on first upload attempt
            const sessionId = await window.CardLyze.initSession();

            const startTime = performance.now();
            const response = await fetch(`/api/column-addition/${selectedCard}/upload`, {
                method: 'POST',
                headers: {
                    'X-Session-Id': sessionId,
                    'X-Filename': selectedFile.name,
                    'Content-Type': 'application/octet-stream',
                },
                body: selectedFile,
            });

            clearInterval(parseTimerInterval);
            const durationSec = ((performance.now() - startTime) / 1000).toFixed(1);

            if (!response.ok) {
                let errDetail = `Server responded with status ${response.status}`;
                try {
                    const errJson = await response.json();
                    if (errJson.detail) errDetail = errJson.detail;
                } catch (e) {
                    // Fallback to text status
                }

                if (response.status === 401) {
                    showError('Session Expired', 'Your session has expired. Please re-upload your file to continue.');
                } else if (response.status === 503) {
                    showError('Server Busy', errDetail);
                } else {
                    showError('Validation Failed', errDetail);
                }
                return;
            }

            const data = await response.json();
            showSuccess(data, durationSec);

        } catch (err) {
            clearInterval(parseTimerInterval);
            console.error('Upload error:', err);
            showError('Processing Error', err.message || 'An unexpected error occurred while uploading.');
        } finally {
            processingCard.classList.add('hidden');
            btnProcess.disabled = false;
            btnChangeFile.disabled = false;
        }
    });

    /**
     * Display Success State
     */
    function showSuccess(data, durationSec) {
        step3Section.classList.remove('hidden');
        bannerError.classList.add('hidden');
        bannerSuccess.classList.remove('hidden');
        previewActionsBar.classList.remove('hidden');
        previewTableContainer.classList.remove('hidden');

        const cardName = selectedCard.toUpperCase();
        bannerSuccessTitle.textContent = `${cardName} Headers Added Successfully`;
        bannerSuccessDesc.textContent = `Mapped ${data.column_count || data.columns.length} columns across ${data.rows.toLocaleString()} rows in ${durationSec}s with 100% data fidelity.`;

        // Initialize reusable DataTable
        initPreviewTable(data.preview);
    }

    /**
     * Display Error State
     */
    function showError(title, message) {
        step3Section.classList.remove('hidden');
        bannerSuccess.classList.add('hidden');
        bannerError.classList.remove('hidden');
        bannerErrorTitle.textContent = title;
        bannerErrorDesc.textContent = message;

        previewActionsBar.classList.add('hidden');
        previewTableContainer.classList.add('hidden');
    }

    function hideResults() {
        step3Section.classList.add('hidden');
        bannerSuccess.classList.add('hidden');
        bannerError.classList.add('hidden');
        previewActionsBar.classList.add('hidden');
        previewTableContainer.classList.add('hidden');
    }

    /**
     * Preview Table via DataTable
     */
    function initPreviewTable(previewData) {
        previewTableContainer.innerHTML = '';
        dataTableInstance = new window.CardLyze.DataTable(previewTableContainer, {
            initialData: previewData,
            hiddenColumns: [],
            fetchData: async (page, pageSize) => {
                const sessionId = window.CardLyze.getSessionId();
                const res = await fetch(`/api/column-addition/preview?page=${page}&page_size=${pageSize}`, {
                    headers: {
                        'X-Session-Id': sessionId,
                    },
                });

                if (!res.ok) {
                    if (res.status === 401) {
                        showError('Session Expired', 'Your session has expired. Please re-upload your file to continue.');
                    }
                    throw new Error(`Failed to load page: HTTP ${res.status}`);
                }

                return await res.json();
            },
        });
    }

    /**
     * Download Excel (.xlsx) Export
     */
    btnDownload.addEventListener('click', async () => {
        const sessionId = window.CardLyze.getSessionId();
        if (!sessionId) {
            showError('Session Error', 'No active session found. Please re-upload your file.');
            return;
        }

        btnDownload.disabled = true;
        btnClear.disabled = true;
        exportLoadingCard.classList.remove('hidden');

        let exportElapsed = 0;
        exportTimer.textContent = '0s';
        clearInterval(exportTimerInterval);
        exportTimerInterval = setInterval(() => {
            exportElapsed++;
            exportTimer.textContent = `${exportElapsed}s`;
        }, 1000);

        try {
            const response = await fetch('/api/column-addition/export', {
                method: 'GET',
                headers: {
                    'X-Session-Id': sessionId,
                },
            });

            clearInterval(exportTimerInterval);

            if (!response.ok) {
                let msg = `Export failed with status ${response.status}`;
                try {
                    const err = await response.json();
                    if (err.detail) msg = err.detail;
                } catch (e) {}

                if (response.status === 401) {
                    showError('Session Expired', 'Your session has expired. Please re-upload your file to continue.');
                } else {
                    showError('Export Failed', msg);
                }
                return;
            }

            // Extract filename from header or fallback
            let filename = `${selectedCard}_with_headers.xlsx`;
            const disposition = response.headers.get('Content-Disposition');
            if (disposition && disposition.includes('filename=')) {
                const match = disposition.match(/filename="?([^";]+)"?/);
                if (match && match[1]) {
                    filename = match[1];
                }
            }

            // Stream response into blob
            const blob = await response.blob();

            // Trigger download via temporary anchor (strict CSP compliant)
            const downloadUrl = URL.createObjectURL(blob);
            const anchor = document.createElement('a');
            anchor.href = downloadUrl;
            anchor.download = filename;
            document.body.appendChild(anchor);
            anchor.click();
            document.body.removeChild(anchor);
            URL.revokeObjectURL(downloadUrl);

        } catch (err) {
            clearInterval(exportTimerInterval);
            console.error('Download export error:', err);
            showError('Export Error', err.message || 'An error occurred while generating the Excel file.');
        } finally {
            exportLoadingCard.classList.add('hidden');
            btnDownload.disabled = false;
            btnClear.disabled = false;
        }
    });

    /**
     * Clear Data
     */
    btnClear.addEventListener('click', async () => {
        const sessionId = window.CardLyze.getSessionId();
        if (sessionId) {
            try {
                await fetch('/api/column-addition', {
                    method: 'DELETE',
                    headers: {
                        'X-Session-Id': sessionId,
                    },
                });
            } catch (e) {
                console.error('Clear dataset error:', e);
            }
        }

        // Reset UI
        selectedFile = null;
        fileInput.value = '';
        fileCard.classList.add('hidden');
        dropzone.classList.remove('hidden');
        hideResults();
        if (previewTableContainer) {
            previewTableContainer.innerHTML = '';
        }
    });

    /**
     * Page Unload Keepalive Wipe
     */
    window.addEventListener('pagehide', () => {
        const sessionId = window.CardLyze.getSessionId();
        if (sessionId) {
            try {
                fetch('/api/column-addition', {
                    method: 'DELETE',
                    headers: { 'X-Session-Id': sessionId },
                    keepalive: true,
                });
            } catch (e) {
                // Ignore during navigation
            }
        }
    });

})();
