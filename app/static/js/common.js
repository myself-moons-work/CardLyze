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
     * Initialize or retrieve an active session token.
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
                        throw new Error('Server is currently at maximum session capacity (10 concurrent users). Please try again shortly.');
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
     * Auto-wipe session on page unload using keepalive/sendBeacon.
     */
    window.addEventListener('pagehide', function () {
        if (currentSessionId) {
            const token = currentSessionId;
            currentSessionId = null;
            try {
                // Send keepalive delete request
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
     * Show indeterminate loading state with file name while parsing in background.
     */
    function showLoadingState(container, fileName) {
        if (!container) return;
        container.innerHTML = `
            <div class="loading-overlay">
                <div class="loading-file-name">Processing: ${escapeHtml(fileName)}</div>
                <div class="progress-bar-indeterminate"></div>
                <div class="loading-status-text">Parsing and validating transaction data...</div>
            </div>
        `;
    }

    function hideLoadingState(container) {
        if (!container) return;
        container.innerHTML = '';
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // Note: Session is created lazily on first upload / API call, not eagerly on page load.

    // Expose CardLyze namespace
    window.CardLyze = {
        initSession,
        getSessionId,
        wipeSession,
        fetchWithSession,
        showLoadingState,
        hideLoadingState,
    };
})(window);

