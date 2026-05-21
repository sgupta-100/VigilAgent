import { useState, useEffect, useRef, useCallback } from 'react';
import { websocketUrl, apiUrl } from '../lib/api';

/**
 * useReconLiveFeed — WebSocket hook for Alpha V6 real-time recon events.
 *
 * Connects to /api/v1/recon/live/{scanId} and accumulates events
 * into structured state for the ReconDashboard component.
 */
export function useReconLiveFeed(scanId) {
    const [connected, setConnected] = useState(false);
    const [events, setEvents] = useState([]);
    const [phases, setPhases] = useState({});
    const [entities, setEntities] = useState({ subdomains: [], endpoints: [], vulns: [], secrets: [] });
    const [tools, setTools] = useState({ running: [], completed: [], failed: [] });
    const [progress, setProgress] = useState({ phase: 'idle', phaseIndex: 0, totalPhases: 0 });
    const [summary, setSummary] = useState(null);
    const wsRef = useRef(null);
    const reconnectRef = useRef(null);

    const connect = useCallback(() => {
        if (!scanId) return;
        const url = websocketUrl(`/api/v1/recon/live/${scanId}`);
        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onopen = () => {
            setConnected(true);
            console.log('[RECON FEED] Connected:', scanId);
        };

        ws.onmessage = (e) => {
            try {
                const event = JSON.parse(e.data);
                handleEvent(event);
            } catch (err) {
                console.warn('[RECON FEED] Parse error:', err);
            }
        };

        ws.onclose = () => {
            setConnected(false);
            // Auto-reconnect after 3s unless scan is complete
            if (!summary) {
                reconnectRef.current = setTimeout(connect, 3000);
            }
        };

        ws.onerror = () => {
            ws.close();
        };
    }, [scanId, summary]);

    const handleEvent = useCallback((event) => {
        const type = event.event_type || event.type;

        // Append to event log (keep last 200)
        setEvents(prev => [...prev.slice(-199), { ...event, _receivedAt: Date.now() }]);

        switch (type) {
            case 'RECON_PHASE_STARTED':
                setProgress(prev => ({
                    ...prev,
                    phase: event.phase,
                    phaseIndex: event.phase_index || prev.phaseIndex,
                    totalPhases: event.total_phases || prev.totalPhases,
                }));
                setPhases(prev => ({
                    ...prev,
                    [event.phase]: { status: 'running', startedAt: Date.now(), tools: event.tools_planned || [] }
                }));
                break;

            case 'RECON_PHASE_COMPLETED':
                setPhases(prev => ({
                    ...prev,
                    [event.phase]: {
                        ...prev[event.phase],
                        status: 'completed',
                        entities_found: event.entities_found,
                        duration_ms: event.duration_ms,
                    }
                }));
                break;

            case 'RECON_TOOL_STARTED':
                setTools(prev => ({
                    ...prev,
                    running: [...prev.running.filter(t => t !== event.tool_name), event.tool_name],
                }));
                break;

            case 'RECON_TOOL_COMPLETED':
                setTools(prev => ({
                    ...prev,
                    running: prev.running.filter(t => t !== event.tool_name),
                    completed: [...prev.completed, event.tool_name],
                    ...(event.status === 'failed' ? { failed: [...prev.failed, event.tool_name] } : {}),
                }));
                break;

            case 'RECON_ENTITY_DISCOVERED':
                setEntities(prev => {
                    const updated = { ...prev };
                    if (event.kind === 'subdomain') updated.subdomains = [...prev.subdomains, event.label];
                    else if (event.kind === 'vulnerability_candidate') updated.vulns = [...prev.vulns, event];
                    else if (event.kind === 'secret') updated.secrets = [...prev.secrets, event];
                    else updated.endpoints = [...prev.endpoints, event];
                    return updated;
                });
                break;

            case 'RECON_VULN_CANDIDATE':
                setEntities(prev => ({ ...prev, vulns: [...prev.vulns, event] }));
                break;

            case 'RECON_COMPLETE':
            case 'scan_complete':
                setSummary(event);
                setProgress(prev => ({ ...prev, phase: 'complete' }));
                break;

            default:
                break;
        }
    }, []);

    useEffect(() => {
        connect();
        return () => {
            if (wsRef.current) wsRef.current.close();
            if (reconnectRef.current) clearTimeout(reconnectRef.current);
        };
    }, [connect]);

    const disconnect = useCallback(() => {
        if (wsRef.current) wsRef.current.close();
        if (reconnectRef.current) clearTimeout(reconnectRef.current);
    }, []);

    return { connected, events, phases, entities, tools, progress, summary, disconnect };
}

/**
 * useReconAPI — REST hooks for starting/stopping/listing recon scans.
 */
export function useReconAPI() {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const startScan = async (targetUrl, mode = 'STANDARD') => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(apiUrl('/api/v1/recon/start'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target_url: targetUrl, mode }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Start failed');
            return data;
        } catch (err) {
            setError(err.message);
            return null;
        } finally {
            setLoading(false);
        }
    };

    const stopScan = async (scanId) => {
        try {
            const res = await fetch(apiUrl(`/api/v1/recon/stop/${scanId}`), { method: 'POST' });
            return await res.json();
        } catch (err) {
            setError(err.message);
            return null;
        }
    };

    const getScanStatus = async (scanId) => {
        try {
            const res = await fetch(apiUrl(`/api/v1/recon/status/${scanId}`));
            return await res.json();
        } catch (err) {
            setError(err.message);
            return null;
        }
    };

    const listScans = async () => {
        try {
            const res = await fetch(apiUrl('/api/v1/recon/scans'));
            return await res.json();
        } catch (err) {
            setError(err.message);
            return [];
        }
    };

    const exportScan = async (scanId, format = 'sarif') => {
        try {
            const res = await fetch(apiUrl('/api/v1/recon/export'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ scan_id: scanId, format }),
            });
            return await res.json();
        } catch (err) {
            setError(err.message);
            return null;
        }
    };

    return { startScan, stopScan, getScanStatus, listScans, exportScan, loading, error };
}
