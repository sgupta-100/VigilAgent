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
