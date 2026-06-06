import { apiUrl } from './api';

/**
 * Trigger auto-download of a generated PDF report from a GI5_LOG WebSocket event.
 * Shared between Dashboard.jsx and Scans.jsx to eliminate duplication.
 *
 * Failure modes (network down, 404, non-PDF response) are surfaced via the
 * optional `toast` callback. Because this helper is invoked from non-component
 * contexts (WebSocket dispatch handlers, refs), it cannot call useToast()
 * directly — callers should pass `toast` from the parent component:
 *
 *   const { toast } = useToast();
 *   handleAutoDownload(data, toast);
 *
 * @param {object}   data    Parsed WebSocket message
 * @param {Function} [toast] Optional toast({ type, title, message }) callback
 * @returns {boolean} true if a download attempt was triggered
 */
export function handleAutoDownload(data, toast) {
    if (
        !data ||
        data.type !== 'GI5_LOG' ||
        typeof data.payload !== 'string' ||
        !data.payload.includes('REPORT GENERATED:')
    ) {
        return false;
    }

    const parts = data.payload.split(/[\\/]/);
    const filename = parts[parts.length - 1];
    if (!filename) {
        notify(toast, { type: 'error', title: 'Report download failed', message: 'Invalid report filename in event payload.' });
        return false;
    }

    const url = apiUrl(`/api/reports/download/${encodeURIComponent(filename)}`);

    // Try a HEAD request first so we can surface 404 / network errors as a
    // toast instead of silently opening a broken tab. If verification passes,
    // we then trigger the actual download via an <a> element (preserves the
    // "Save As" filename behaviour browsers give us for direct nav).
    verifyAndDownload(url, filename, toast);
    return true;
}

function notify(toast, payload) {
    if (typeof toast === 'function') {
        try { toast(payload); } catch (e) { /* swallow — UI shouldn't crash on toast */ }
    }
    // No toast callback — swallow silently to avoid noisy console output.
}

async function verifyAndDownload(url, filename, toast) {
    let res;
    try {
        res = await fetch(url, { method: 'HEAD' });
    } catch (err) {
        notify(toast, {
            type: 'error',
            title: 'Report download failed',
            message: 'Network error reaching the report endpoint. Check the backend connection.',
        });
        return;
    }

    if (!res.ok) {
        const reason = res.status === 404
            ? 'Report file not found on the server (404).'
            : `Server returned HTTP ${res.status} when fetching the report.`;
        notify(toast, { type: 'error', title: 'Report download failed', message: reason });
        return;
    }

    // Best-effort content-type sanity check — warn (don't block) if the
    // server didn't tag it as a PDF.
    const ctype = (res.headers.get('content-type') || '').toLowerCase();
    if (ctype && !ctype.includes('pdf') && !ctype.includes('octet-stream')) {
        notify(toast, {
            type: 'warning',
            title: 'Unexpected report format',
            message: `Server returned ${ctype} — file may not be a valid PDF.`,
        });
    }

    triggerBrowserDownload(url, filename);
    notify(toast, {
        type: 'success',
        title: 'Report ready',
        message: `Downloading ${filename}...`,
    });
}

function triggerBrowserDownload(url, filename) {
    const a = document.createElement('a');
    a.href = url;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}
