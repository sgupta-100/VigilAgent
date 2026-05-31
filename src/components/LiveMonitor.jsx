import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import { resolveAgent } from '../lib/agentNames';

/**
 * LiveMonitor — real-time backend agent activity feed.
 *
 * Subscribes to the shared singleton WebSocket (managed by useWebSocket) and
 * renders the events the backend's socket_manager broadcasts during a scan:
 *   LIVE_ATTACK_FEED, LIVE_THREAT_LOG, JOB_ASSIGNED, RECON_PACKET,
 *   COVERAGE_UPDATE, PHASE_STARTED, PHASE_COMPLETED, AGENT_STATUS, VULN_CONFIRMED.
 *
 * Behaviour:
 *   - Auto-scrolls to the newest entry (capped at 200 entries).
 *   - 3 status chips: connection state, current phase, total events.
 *   - Resolves agent IDs to friendly names via lib/agentNames.
 *   - Color-codes each event by type/severity.
 */

const MAX_ENTRIES = 200;

const RELEVANT_TYPES = new Set([
    'LIVE_ATTACK_FEED',
    'LIVE_THREAT_LOG',
    'JOB_ASSIGNED',
    'RECON_PACKET',
    'COVERAGE_UPDATE',
    'PHASE_STARTED',
    'PHASE_COMPLETED',
    'AGENT_STATUS',
    'VULN_CONFIRMED',
]);

// Tailwind color classes per event type. Severity overrides this when present.
const TYPE_COLORS = {
    LIVE_ATTACK_FEED: 'text-orange-300 border-orange-500/30',
    LIVE_THREAT_LOG: 'text-pink-300 border-pink-500/30',
    JOB_ASSIGNED: 'text-blue-300 border-blue-500/30',
    RECON_PACKET: 'text-cyan-300 border-cyan-500/30',
    COVERAGE_UPDATE: 'text-teal-300 border-teal-500/30',
    PHASE_STARTED: 'text-purple-300 border-purple-500/30',
    PHASE_COMPLETED: 'text-purple-200 border-purple-500/40',
    AGENT_STATUS: 'text-indigo-300 border-indigo-500/30',
    VULN_CONFIRMED: 'text-red-300 border-red-500/40',
};

const SEVERITY_COLORS = {
    CRITICAL: 'text-red-300 border-red-500/50',
    HIGH: 'text-orange-300 border-orange-500/40',
    MEDIUM: 'text-yellow-300 border-yellow-500/40',
    LOW: 'text-blue-300 border-blue-500/30',
    INFO: 'text-gray-300 border-white/10',
};

const formatTime = (ts) => {
    if (!ts) return new Date().toLocaleTimeString();
    if (typeof ts === 'string' && ts.includes(':')) return ts;
    try {
        const d = typeof ts === 'number' ? new Date(ts * (ts > 1e12 ? 1 : 1000)) : new Date(ts);
        if (Number.isNaN(d.getTime())) return new Date().toLocaleTimeString();
        return d.toLocaleTimeString();
    } catch {
        return new Date().toLocaleTimeString();
    }
};

const truncate = (s, n) => {
    if (typeof s !== 'string') return s;
    return s.length > n ? `${s.slice(0, n - 1)}…` : s;
};

// Build a compact one-liner for the event payload so the feed stays scannable.
const summarizeEvent = (evt) => {
    const p = evt.payload || {};
    switch (evt.type) {
        case 'PHASE_STARTED':
            return `Phase started: ${p.phase || p.name || 'unknown'}`;
        case 'PHASE_COMPLETED':
            return `Phase completed: ${p.phase || p.name || 'unknown'}`;
        case 'AGENT_STATUS':
            return `Status: ${p.status || p.state || 'update'}${p.task ? ` · ${p.task}` : ''}`;
        case 'JOB_ASSIGNED':
            return `Job → ${p.agent || p.target_agent || 'agent'}: ${p.job_type || p.task || p.description || 'task'}`;
        case 'RECON_PACKET':
            return `Recon ${p.method ? `${p.method} ` : ''}${p.url || p.target || 'endpoint'}`;
        case 'COVERAGE_UPDATE':
            return `Coverage ${p.percent ?? p.coverage ?? '?'}% · ${p.endpoints_seen ?? p.count ?? '0'} endpoints`;
        case 'LIVE_ATTACK_FEED':
            return `${p.arsenal || p.threat_type || 'Attack'} → ${p.url || p.target || 'target'} ${p.result ? `· ${p.result}` : ''}`;
        case 'LIVE_THREAT_LOG':
            return `${p.threat_type || 'Threat'} · ${p.url || p.message || ''}`;
        case 'VULN_CONFIRMED':
            return `${p.severity || 'VULN'} · ${p.type || p.title || 'finding'} @ ${p.url || p.id || 'target'}`;
        default:
            if (typeof p === 'string') return truncate(p, 120);
            return truncate(JSON.stringify(p), 120);
    }
};

const LiveMonitor = () => {
    const { subscribe, isConnected: wsInitiallyConnected } = useWebSocket();
    const [entries, setEntries] = useState([]); // newest first
    const [isConnected, setIsConnected] = useState(Boolean(wsInitiallyConnected));
    const [currentPhase, setCurrentPhase] = useState(null);
    const [totalEvents, setTotalEvents] = useState(0);
    const [autoScroll, setAutoScroll] = useState(true);

    const listRef = useRef(null);
    const totalRef = useRef(0);

    useEffect(() => {
        const unsub = subscribe((data) => {
            if (!data || typeof data !== 'object') return;

            // Connection-state hints arrive as their own events; the hook also
            // tracks state internally, but mirror a few of them locally.
            if (data.type === 'CONNECTED' || data.type === 'WS_OPEN') {
                setIsConnected(true);
                return;
            }
            if (data.type === 'DISCONNECTED' || data.type === 'WS_CLOSED') {
                setIsConnected(false);
                return;
            }

            if (!RELEVANT_TYPES.has(data.type)) return;

            // Track current phase from PHASE_* events.
            if (data.type === 'PHASE_STARTED') {
                setCurrentPhase(data.payload?.phase || data.payload?.name || 'unknown');
            } else if (data.type === 'PHASE_COMPLETED') {
                setCurrentPhase((prev) => {
                    const completed = data.payload?.phase || data.payload?.name;
                    if (!prev || !completed || prev === completed) return null;
                    return prev;
                });
            }

            const payload = data.payload || {};
            const sev = (payload.severity || '').toUpperCase();
            const colorClass = SEVERITY_COLORS[sev] || TYPE_COLORS[data.type] || 'text-gray-300 border-white/10';

            const agentId = data.source || payload.agent || payload.source || 'system';
            const agent = resolveAgent(agentId);

            const entry = {
                id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
                timestamp: formatTime(payload.timestamp || data.timestamp),
                agentId,
                agentName: agent.name,
                agentColor: agent.color,
                type: data.type,
                message: summarizeEvent(data),
                colorClass,
            };

            totalRef.current += 1;
            setTotalEvents(totalRef.current);
            setEntries((prev) => {
                const next = [entry, ...prev];
                return next.length > MAX_ENTRIES ? next.slice(0, MAX_ENTRIES) : next;
            });

            // Once any backend event arrives, the WS is definitionally up.
            setIsConnected(true);
        });

        return () => { try { unsub(); } catch { /* noop */ } };
    }, [subscribe]);

    // Auto-scroll: because newest-first, "newest" is at the top of the list,
    // so we just keep the scroll position pinned to scrollTop = 0.
    useEffect(() => {
        if (!autoScroll) return;
        const el = listRef.current;
        if (el) el.scrollTop = 0;
    }, [entries, autoScroll]);

    const connectionChip = useMemo(() => {
        return isConnected
            ? { label: 'CONNECTED', color: 'bg-green-500/15 text-green-300 border-green-500/30', dot: 'bg-green-400' }
            : { label: 'OFFLINE', color: 'bg-red-500/15 text-red-300 border-red-500/30', dot: 'bg-red-400' };
    }, [isConnected]);

    return (
        <div className="glass-panel-dash rounded-2xl overflow-hidden flex flex-col h-[400px]">
            <div className="flex items-center justify-between px-5 py-3 border-b border-white/5">
                <h2 className="text-sm font-medium text-gray-200 flex items-center gap-2">
                    <span className="material-symbols-outlined text-base text-purple-400">graphic_eq</span>
                    Live Threat Monitoring
                </h2>
                <div className="flex items-center gap-2">
                    <span
                        className={`flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wide px-2 py-0.5 rounded-full border ${connectionChip.color}`}
                        title="WebSocket connection"
                    >
                        <span className={`w-1.5 h-1.5 rounded-full ${connectionChip.dot} ${isConnected ? 'animate-pulse' : ''}`}></span>
                        {connectionChip.label}
                    </span>
                    <span
                        className="text-[10px] font-mono uppercase tracking-wide px-2 py-0.5 rounded-full border bg-purple-500/15 text-purple-300 border-purple-500/30"
                        title="Current orchestrator phase"
                    >
                        {currentPhase ? `Phase: ${currentPhase}` : 'Phase: idle'}
                    </span>
                    <span
                        className="text-[10px] font-mono uppercase tracking-wide px-2 py-0.5 rounded-full border bg-cyan-500/15 text-cyan-300 border-cyan-500/30"
                        title="Total events received this session"
                    >
                        {totalEvents} events
                    </span>
                    <button
                        onClick={() => setAutoScroll((v) => !v)}
                        className={`text-[10px] font-mono uppercase tracking-wide px-2 py-0.5 rounded-full border transition-colors ${autoScroll
                            ? 'bg-white/10 text-gray-200 border-white/20'
                            : 'bg-white/5 text-gray-500 border-white/10 hover:text-gray-300'
                            }`}
                        title="Toggle auto-scroll to newest"
                    >
                        {autoScroll ? 'auto-scroll on' : 'auto-scroll off'}
                    </button>
                </div>
            </div>

            <div ref={listRef} className="flex-grow overflow-y-auto scrollbar-thin">
                {entries.length === 0 ? (
                    <div className="flex items-center justify-center h-full text-gray-600 opacity-40">
                        <div className="text-center">
                            <span className="material-symbols-outlined text-3xl block mb-2">graphic_eq</span>
                            <p className="text-xs font-mono">Waiting for agent activity…</p>
                        </div>
                    </div>
                ) : (
                    <ul className="divide-y divide-white/5">
                        {entries.map((e) => (
                            <li
                                key={e.id}
                                className={`px-5 py-2 text-xs font-mono flex items-start gap-3 hover:bg-white/[0.02] border-l-2 ${e.colorClass}`}
                            >
                                <span className="text-gray-500 shrink-0 w-20">{e.timestamp}</span>
                                <span className={`shrink-0 w-32 truncate ${e.agentColor}`} title={e.agentId}>
                                    {e.agentName}
                                </span>
                                <span className="shrink-0 w-36 truncate text-gray-300" title={e.type}>
                                    {e.type}
                                </span>
                                <span className="flex-grow truncate text-gray-200" title={e.message}>
                                    {e.message}
                                </span>
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </div>
    );
};

export default LiveMonitor;
