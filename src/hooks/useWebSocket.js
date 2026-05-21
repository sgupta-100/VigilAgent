import { useEffect, useRef, useCallback } from 'react';
import { websocketUrl } from '../lib/api';

/**
 * App-level singleton WebSocket manager.
 * All pages share one connection instead of each opening their own.
 *
 * Usage:
 *   const { subscribe, isConnected } = useWebSocket();
 *   useEffect(() => subscribe((data) => { ... }), [subscribe]);
 */

// ── Module-level singleton state ──
let _ws = null;
let _listeners = new Set();
let _reconnectTimer = null;
let _connected = false;
let _connectListeners = new Set();

function _notifyConnect(state) {
    _connected = state;
    _connectListeners.forEach(fn => fn(state));
}

function _dispatch(data) {
    _listeners.forEach(fn => {
        try { fn(data); } catch (e) { console.error('[useWebSocket] listener error', e); }
    });
}

function _connect() {
    if (_ws && (_ws.readyState === WebSocket.CONNECTING || _ws.readyState === WebSocket.OPEN)) {
        return; // already connected or connecting
    }

    try {
        _ws = new WebSocket(websocketUrl('/stream', { client_type: 'ui' }));
    } catch (e) {
        console.error('[useWebSocket] Failed to create WebSocket', e);
        _scheduleReconnect();
        return;
    }

    _ws.onopen = () => {
        console.log('[WS] Connected to backend stream');
        _notifyConnect(true);
    };

    _ws.onmessage = (event) => {
        try {
            const parsed = JSON.parse(event.data);
            if (parsed.type === 'BATCH' && Array.isArray(parsed.payload)) {
                parsed.payload.forEach(_dispatch);
            } else {
                _dispatch(parsed);
            }
        } catch (e) {
            console.error('[WS] Parse error', e);
        }
    };

    _ws.onclose = () => {
        console.log('[WS] Disconnected. Reconnecting in 3s...');
        _notifyConnect(false);
        _scheduleReconnect();
    };

    _ws.onerror = () => {
        // onclose will fire after this
    };
}

function _scheduleReconnect() {
    clearTimeout(_reconnectTimer);
    _reconnectTimer = setTimeout(_connect, 3000);
}

function _ensureConnection() {
    if (!_ws || _ws.readyState === WebSocket.CLOSED || _ws.readyState === WebSocket.CLOSING) {
        _connect();
    }
}

/**
 * React hook — subscribe to WebSocket messages.
 * The connection is opened on first subscriber and kept alive across page navigations.
 *
 * @returns {{ subscribe: (cb: Function) => () => void, isConnected: boolean }}
 */
export function useWebSocket() {
    const connectedRef = useRef(_connected);

    useEffect(() => {
        _ensureConnection();

        const onConnect = (state) => { connectedRef.current = state; };
        _connectListeners.add(onConnect);

        return () => {
            _connectListeners.delete(onConnect);
        };
    }, []);

    /**
     * Subscribe to all incoming WS messages.
     * Returns an unsubscribe function.
     */
    const subscribe = useCallback((callback) => {
        _listeners.add(callback);
        _ensureConnection();
        return () => {
            _listeners.delete(callback);
        };
    }, []);

    return { subscribe, isConnected: connectedRef.current };
}
