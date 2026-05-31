const normalizeBaseUrl = (value) => value.replace(/\/+$/, '');
const normalizePath = (path) => (path.startsWith('/') ? path : `/${path}`);

const getDefaultBackendHost = () => {
    const { hostname } = window.location;
    if (hostname === 'localhost') return 'localhost:8000';
    if (hostname === '127.0.0.1') return '127.0.0.1:8000';
    return `${hostname}:8000`;
};

const apiBaseFromEnv = import.meta.env.VITE_API_BASE_URL;
const wsBaseFromEnv = import.meta.env.VITE_WS_BASE_URL;

export const API_BASE_URL = normalizeBaseUrl(
    apiBaseFromEnv || `${window.location.protocol}//${getDefaultBackendHost()}`
);

export const WS_BASE_URL = normalizeBaseUrl(
    wsBaseFromEnv || `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${getDefaultBackendHost()}`
);

export const getWsToken = () => localStorage.getItem('vulagent_ws_token') || '';

export const apiUrl = (path) => `${API_BASE_URL}${normalizePath(path)}`;

export const websocketUrl = (path, params = {}) => {
    const url = new URL(`${WS_BASE_URL}${normalizePath(path)}`);
    Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
            url.searchParams.set(key, value);
        }
    });

    const token = getWsToken();
    if (token && !url.searchParams.has('token')) {
        url.searchParams.set('token', token);
    }

    return url.toString();
};

// ── Hidden-scans (frontend-only "wipe history") ──
// These IDs are filtered out of the Scans view; backend storage is untouched.
const HIDDEN_SCANS_KEY = 'vigilagent.hiddenScans';

export const getHiddenScanIds = () => {
    try {
        const raw = localStorage.getItem(HIDDEN_SCANS_KEY);
        if (!raw) return [];
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed.filter((v) => typeof v === 'string') : [];
    } catch {
        return [];
    }
};

export const setHiddenScanIds = (ids) => {
    try {
        const unique = Array.from(new Set((ids || []).filter((v) => typeof v === 'string')));
        localStorage.setItem(HIDDEN_SCANS_KEY, JSON.stringify(unique));
        return unique;
    } catch {
        return [];
    }
};

export const addHiddenScanIds = (ids) => {
    const current = getHiddenScanIds();
    return setHiddenScanIds([...current, ...(ids || [])]);
};

export const clearHiddenScanIds = () => {
    try { localStorage.removeItem(HIDDEN_SCANS_KEY); } catch { /* noop */ }
};

// ── Scan creation (POST /api/scans) ──
// Backend returns 202 with { scan_id, status }. We surface a clear error message
// on non-2xx responses so the caller can show it inline.
export const createScan = async ({ target_url, mode = 'STANDARD', modules = [] }) => {
    const url = apiUrl('/api/scans');
    let response;
    try {
        response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target_url, mode, modules }),
        });
    } catch (err) {
        const msg = err && err.message ? err.message : 'Network error';
        const e = new Error(`Failed to reach backend: ${msg}`);
        e.cause = err;
        throw e;
    }

    let body = null;
    try { body = await response.json(); } catch { /* keep null */ }

    if (!response.ok) {
        const detail = (body && (body.detail || body.message)) || `HTTP ${response.status}`;
        const e = new Error(`Scan creation failed: ${detail}`);
        e.status = response.status;
        e.body = body;
        throw e;
    }

    return body || {};
};
