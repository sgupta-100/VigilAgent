import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useReconLiveFeed, useReconAPI } from '../hooks/useReconFeed';

const PHASE_LABELS = {
    idle: 'Waiting',
    initialization: 'Initializing',
    passive_intelligence: 'Passive Recon',
    dns_infrastructure: 'DNS & Infrastructure',
    http_browser_intelligence: 'HTTP & Browser',
    directory_route_discovery: 'Directory Discovery',
    api_reconnaissance: 'API Recon',
    visual_documentation: 'Visual Docs',
    template_validation: 'Validation',
    complete: 'Complete',
};

const SEVERITY_COLORS = {
    critical: '#ff3b5c', high: '#ff6b35', medium: '#ffb347', low: '#7dd3fc', info: '#94a3b8',
};

/* ── Recon Dashboard ───────────────────────────────── */
export default function ReconDashboard({ navigate }) {
    const [targetUrl, setTargetUrl] = useState('');
    const [scanMode, setScanMode] = useState('STANDARD');
    const [activeScanId, setActiveScanId] = useState(null);
    const { startScan, stopScan, loading, error: apiError } = useReconAPI();
    const feed = useReconLiveFeed(activeScanId);

    const handleStart = async () => {
        if (!targetUrl.trim()) return;
        const result = await startScan(targetUrl, scanMode);
        if (result?.scan_id) setActiveScanId(result.scan_id);
    };

    const handleStop = async () => {
        if (activeScanId) await stopScan(activeScanId);
    };

    return (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            style={{ minHeight: '100vh', padding: '24px 32px', color: '#e2e8f0', fontFamily: 'Inter, sans-serif' }}>

            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 28 }}>
                <button onClick={() => navigate('dashboard')}
                    style={{ background: 'rgba(255,255,255,0.06)', border: 'none', color: '#94a3b8',
                        borderRadius: 8, padding: '8px 14px', cursor: 'pointer', fontSize: 14 }}>
                    ← Back
                </button>
                <h1 style={{ fontSize: 28, fontWeight: 700, margin: 0,
                    background: 'linear-gradient(135deg, #6366f1, #a855f7)', WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent' }}>
                    Alpha V6 — Recon Engine
                </h1>
                {feed.connected && (
                    <span style={{ background: '#22c55e', width: 8, height: 8, borderRadius: '50%',
                        display: 'inline-block', boxShadow: '0 0 8px #22c55e' }} />
                )}
            </div>

            {/* Target Input */}
            {!activeScanId && (
                <div style={{ background: 'rgba(255,255,255,0.04)', borderRadius: 16, padding: 24,
                    border: '1px solid rgba(255,255,255,0.08)', marginBottom: 24 }}>
                    <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                        <input type="text" placeholder="https://target.example.com" value={targetUrl}
                            onChange={e => setTargetUrl(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && handleStart()}
                            style={{ flex: 1, padding: '12px 16px', borderRadius: 10,
                                background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.1)',
                                color: '#e2e8f0', fontSize: 15, outline: 'none' }} />
                        <select value={scanMode} onChange={e => setScanMode(e.target.value)}
                            style={{ padding: '12px 16px', borderRadius: 10, background: 'rgba(0,0,0,0.3)',
                                border: '1px solid rgba(255,255,255,0.1)', color: '#e2e8f0', fontSize: 14 }}>
                            <option value="PASSIVE_ONLY">Passive Only</option>
                            <option value="STANDARD">Standard</option>
                            <option value="AGGRESSIVE">Aggressive</option>
                        </select>
                        <button onClick={handleStart} disabled={loading || !targetUrl.trim()}
                            style={{ padding: '12px 28px', borderRadius: 10, fontWeight: 600, fontSize: 15,
                                border: 'none', cursor: loading ? 'wait' : 'pointer',
                                background: 'linear-gradient(135deg, #6366f1, #a855f7)', color: '#fff',
                                opacity: loading ? 0.6 : 1 }}>
                            {loading ? 'Starting...' : 'Launch Recon'}
                        </button>
                    </div>
                    {apiError && <p style={{ color: '#ff3b5c', margin: '12px 0 0', fontSize: 13 }}>{apiError}</p>}
                </div>
            )}

            {/* Active Scan Dashboard */}
            {activeScanId && (
                <>
                    {/* Phase Progress Bar */}
                    <PhaseProgressBar phases={feed.phases} current={feed.progress.phase} />

                    {/* Stats Grid */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
                        gap: 14, marginBottom: 24 }}>
                        <StatCard label="Subdomains" value={feed.entities.subdomains.length} icon="dns" color="#6366f1" />
                        <StatCard label="Endpoints" value={feed.entities.endpoints.length} icon="api" color="#a855f7" />
                        <StatCard label="Vulns" value={feed.entities.vulns.length} icon="bug_report" color="#ff3b5c" />
                        <StatCard label="Secrets" value={feed.entities.secrets.length} icon="key" color="#f59e0b" />
                        <StatCard label="Tools Run" value={feed.tools.completed.length} icon="build" color="#22c55e" />
                        <StatCard label="Running" value={feed.tools.running.length} icon="sync" color="#3b82f6" anim />
                    </div>

                    {/* Two-column layout */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                        {/* Live Event Log */}
                        <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 14, padding: 18,
                            border: '1px solid rgba(255,255,255,0.06)', maxHeight: 420, overflowY: 'auto' }}>
                            <h3 style={{ fontSize: 15, fontWeight: 600, margin: '0 0 12px', color: '#94a3b8' }}>
                                Live Event Stream
                            </h3>
                            <AnimatePresence>
                                {feed.events.slice(-30).reverse().map((evt, i) => (
                                    <motion.div key={i} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
                                        style={{ padding: '6px 0', borderBottom: '1px solid rgba(255,255,255,0.04)',
                                            fontSize: 12, fontFamily: 'monospace', color: '#94a3b8' }}>
                                        <span style={{ color: eventColor(evt.event_type || evt.type) }}>
                                            [{(evt.event_type || evt.type || '').replace('RECON_', '')}]
                                        </span>
                                        {' '}{evt.tool_name || evt.phase || evt.label || evt.name || ''}
                                    </motion.div>
                                ))}
                            </AnimatePresence>
                        </div>

                        {/* Vulnerability Findings */}
                        <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 14, padding: 18,
                            border: '1px solid rgba(255,255,255,0.06)', maxHeight: 420, overflowY: 'auto' }}>
                            <h3 style={{ fontSize: 15, fontWeight: 600, margin: '0 0 12px', color: '#94a3b8' }}>
                                Vulnerability Candidates
                            </h3>
                            {feed.entities.vulns.length === 0 ? (
                                <p style={{ fontSize: 13, color: '#475569' }}>No vulnerabilities found yet...</p>
                            ) : (
                                feed.entities.vulns.map((v, i) => (
                                    <div key={i} style={{ padding: '8px 12px', marginBottom: 6, borderRadius: 8,
                                        background: `${SEVERITY_COLORS[v.severity] || '#475569'}15`,
                                        borderLeft: `3px solid ${SEVERITY_COLORS[v.severity] || '#475569'}` }}>
                                        <div style={{ fontSize: 13, fontWeight: 600, color: '#e2e8f0' }}>
                                            {v.name || v.label}
                                        </div>
                                        <div style={{ fontSize: 11, color: '#94a3b8' }}>
                                            {v.target || v.source_tool} · {v.severity?.toUpperCase()}
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>

                    {/* Stop Button */}
                    <div style={{ marginTop: 20, display: 'flex', gap: 12 }}>
                        <button onClick={handleStop}
                            style={{ padding: '10px 24px', borderRadius: 10, background: 'rgba(255,59,92,0.15)',
                                border: '1px solid rgba(255,59,92,0.3)', color: '#ff3b5c', fontWeight: 600,
                                cursor: 'pointer' }}>
                            Stop Scan
                        </button>
                        {feed.summary && (
                            <button onClick={() => { setActiveScanId(null); setTargetUrl(''); }}
                                style={{ padding: '10px 24px', borderRadius: 10, background: 'rgba(99,102,241,0.15)',
                                    border: '1px solid rgba(99,102,241,0.3)', color: '#6366f1', fontWeight: 600,
                                    cursor: 'pointer' }}>
                                New Scan
                            </button>
                        )}
                    </div>
                </>
            )}
        </motion.div>
    );
}

/* ── Sub-components ────────────────────────────────── */

function StatCard({ label, value, icon, color, anim }) {
    return (
        <motion.div animate={anim ? { scale: [1, 1.02, 1] } : {}}
            transition={anim ? { repeat: Infinity, duration: 1.5 } : {}}
            style={{ background: 'rgba(255,255,255,0.04)', borderRadius: 12, padding: '16px 18px',
                border: '1px solid rgba(255,255,255,0.06)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <span className="material-icons-outlined" style={{ fontSize: 18, color }}>{icon}</span>
                <span style={{ fontSize: 12, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: 0.5 }}>{label}</span>
            </div>
            <div style={{ fontSize: 28, fontWeight: 700, color }}>{value}</div>
        </motion.div>
    );
}

function PhaseProgressBar({ phases, current }) {
    const phaseOrder = [
        'passive_intelligence', 'dns_infrastructure', 'http_browser_intelligence',
        'directory_route_discovery', 'api_reconnaissance', 'visual_documentation', 'template_validation',
    ];
    return (
        <div style={{ display: 'flex', gap: 4, marginBottom: 24 }}>
            {phaseOrder.map(p => {
                const state = phases[p]?.status || 'pending';
                const isCurrent = p === current;
                return (
                    <div key={p} style={{ flex: 1, position: 'relative' }}>
                        <div style={{
                            height: 6, borderRadius: 3,
                            background: state === 'completed' ? '#22c55e'
                                : isCurrent ? 'linear-gradient(90deg, #6366f1, #a855f7)'
                                : 'rgba(255,255,255,0.08)',
                            transition: 'all 0.4s ease',
                            ...(isCurrent ? { boxShadow: '0 0 12px rgba(99,102,241,0.4)' } : {}),
                        }} />
                        <div style={{ fontSize: 9, color: isCurrent ? '#a855f7' : '#475569',
                            textAlign: 'center', marginTop: 4, fontWeight: isCurrent ? 600 : 400 }}>
                            {PHASE_LABELS[p]?.replace(' ', '\n') || p}
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

function eventColor(type) {
    if (!type) return '#475569';
    if (type.includes('COMPLETE')) return '#22c55e';
    if (type.includes('STARTED')) return '#3b82f6';
    if (type.includes('VULN')) return '#ff3b5c';
    if (type.includes('SECRET')) return '#f59e0b';
    if (type.includes('SCOPE')) return '#ef4444';
    if (type.includes('ENTITY')) return '#a855f7';
    return '#64748b';
}
