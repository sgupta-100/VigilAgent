import { apiUrl } from './api';

/**
 * Trigger auto-download of a generated PDF report from a GI5_LOG WebSocket event.
 * Shared between Dashboard.jsx and Scans.jsx to eliminate duplication.
 *
 * @param {object} data - Parsed WebSocket message
 * @returns {boolean} true if a download was triggered
 */
export function handleAutoDownload(data) {
    if (
        data.type === 'GI5_LOG' &&
        data.payload &&
        typeof data.payload === 'string' &&
        data.payload.includes('REPORT GENERATED:')
    ) {
        const parts = data.payload.split(/[\\/]/);
        const filename = parts[parts.length - 1];
        const url = apiUrl(`/api/reports/download/${encodeURIComponent(filename)}`);

        const a = document.createElement('a');
        a.href = url;
        a.target = '_blank';
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        return true;
    }
    return false;
}
