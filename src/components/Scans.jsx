import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Navigation from './Navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { LIQUID_SPRING } from '../lib/constants';
import {
    apiUrl,
    getHiddenScanIds,
    addHiddenScanIds,
    clearHiddenScanIds,
} from '../lib/api';
import { handleAutoDownload } from '../lib/downloadReport';
import { useWebSocket } from '../hooks/useWebSocket';

const Scans = ({ navigate }) => {
    const starsRef = useRef(null);

    const [scans, setScans] = useState([]);
    const [hiddenIds, setHiddenIds] = useState(() => getHiddenScanIds());
    const [progressMap, setProgressMap] = useState({}); // Real-time report progress
    const messageBuffer = useRef([]);
    const lastFlush = useRef(Date.now());
    const { subscribe } = useWebSocket();
    const scansRef = useRef(scans);
    const progressMapRef = useRef(progressMap);
    const hiddenIdsRef = useRef(hiddenIds);

    useEffect(() => { scansRef.current = scans; }, [scans]);
    useEffect(() => { progressMapRef.current = progressMap; }, [progressMap]);
    useEffect(() => { hiddenIdsRef.current = hiddenIds; }, [hiddenIds]);

    // Visible scans = backend list minus locally hidden ids. Backend storage is untouched.
    const visibleScans = useMemo(() => {
        if (!hiddenIds.length) return scans;
        const hide = new Set(hiddenIds);
        return scans.filter((s) => !hide.has(s.id));
    }, [scans, hiddenIds]);

    const fetchScans = useCallback(async () => {
        try {
            const res = await fetch(apiUrl('/api/dashboard/scans'));
            const data = await res.json();
            setScans(Array.isArray(data) ? data : []);
        } catch (err) {
            // console.error("Failed to fetch scans:", err);
        }
    }, []);

    // Shared WebSocket subscription & Initial Fetch
    useEffect(() => {
        fetchScans();

        const flushBuffer = () => {
            if (messageBuffer.current.length === 0) return;

            const messages = [...messageBuffer.current];
            messageBuffer.current = [];

            let shouldFetch = false;
            const currentProgress = progressMapRef.current;
            const newProgress = { ...currentProgress };

            messages.forEach(data => {
                // 1. Progress Updates (SCAN_UPDATE with progress field)
                if (data.type === 'SCAN_UPDATE' && data.payload?.progress) {
                    newProgress[data.payload.id] = data.payload.progress;
                }

                // 2. Scan Status Update (Trigger Fetch)
                if (['SCAN_UPDATE', 'GI5_COMPLETE', 'REPORT_READY'].includes(data.type)) {
                    shouldFetch = true;
                }

                // 3. Auto-download generated PDF report (shared utility)
                if (data.type === 'GI5_LOG') {
                    handleAutoDownload(data);
                }
            });

            if (Object.keys(newProgress).length > Object.keys(currentProgress).length ||
                JSON.stringify(newProgress) !== JSON.stringify(currentProgress)) {
                setProgressMap(prev => ({ ...prev, ...newProgress }));
            }

            if (shouldFetch) {
                fetchScans();
            }
        };

        const throttleInterval = setInterval(flushBuffer, 800);

        // Subscribe to shared singleton WS (no per-page connection)
        const unsub = subscribe((data) => {
            messageBuffer.current.push(data);
        });

        // --- FIXED POLLING: Check for both Finalizing and Completed-not-ready ---
        const pollInterval = setInterval(() => {
            const needsRefresh = scansRef.current.some(s =>
                s.status === 'Finalizing' ||
                (s.status === 'Completed' && !s.report_ready)
            );
            if (needsRefresh) {
                fetchScans();
            }
        }, 5000);

        return () => {
            unsub();
            clearInterval(pollInterval);
            clearInterval(throttleInterval);
        };
    }, [fetchScans, subscribe]);

    // Live Duration Timer - Removed (Was causing lag and excessive re-renders)
    // useEffect(() => { ... }, []);

    // Stars effect moved to GlobalBackground
    // useEffect(() => {
    //     if (starsRef.current) {
    //        ... removed ...
    //     }
    // }, []);

    const [downloading, setDownloading] = useState(null); // Track which scan is downloading

    // Frontend-only "Wipe History": hides all currently listed scans from THIS view.
    // Backend records, reports, and forensic data are NOT touched.
    const handleWipeHistory = () => {
        if (!confirm("Hide all current scans from this view? (Backend records stay intact.)")) return;

        const idsToHide = scansRef.current.map((s) => s.id).filter(Boolean);
        const next = addHiddenScanIds(idsToHide);
        setHiddenIds(next);
        hiddenIdsRef.current = next;

        // Reset transient view-only progress; backend data is left alone.
        setProgressMap({});
        messageBuffer.current = [];
    };

    // UX nicety: clears the locally hidden set so previously hidden scans reappear.
    const handleShowHidden = () => {
        clearHiddenScanIds();
        setHiddenIds([]);
        hiddenIdsRef.current = [];
    };

    const handleDownloadPdf = async (scanId) => {
        setDownloading(scanId);
        try {
            const response = await fetch(apiUrl(`/api/reports/pdf/${scanId}`));
            if (!response.ok) throw new Error('Download failed');

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `scan_report_${scanId}.pdf`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (error) {
            // console.error('Error downloading PDF:', error);
            alert('Failed to download PDF report. Ensure backend is running.');
        } finally {
            setDownloading(null);
        }
    };

    return (
        <div className="min-h-screen relative overflow-x-hidden text-gray-200">
            <div className="stars-container fixed top-0 left-0 w-full h-full z-[-1] overflow-hidden pointer-events-none"></div>

            <div className="relative z-10 flex flex-col min-h-screen">
                <Navigation navigate={navigate} activePage="scans" />

                <main className="relative z-10 max-w-7xl mx-auto px-6 lg:px-8 py-8 w-full flex-grow">
                    <motion.div
                        initial={{ opacity: 0, y: -20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ ...LIQUID_SPRING, duration: 0.5 }}
                        className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8"
                    >
                        <div>
                            <h1 className="text-[32px] font-semibold text-white mb-2">Scans</h1>
                            <p className="text-gray-400 text-sm font-light tracking-wide opacity-80">View and manage your past and running security assessments.</p>
                        </div>
                        <div className="flex bg-black/20 p-1 rounded-xl border border-white/5 shadow-inner self-start md:self-end">
                            <motion.button
                                whileHover={{ scale: 1.02 }}
                                whileTap={{ scale: 0.98 }}
                                onClick={handleWipeHistory}
                                title="Hide all listed scans from this view. Backend records remain intact."
                                className="px-4 py-2 rounded-lg text-xs font-medium text-gray-300 hover:text-white hover:bg-white/10 transition-all flex items-center gap-2"
                            >
                                <span className="material-symbols-outlined text-sm">visibility_off</span>
                                Wipe History
                            </motion.button>
                            {hiddenIds.length > 0 && (
                                <motion.button
                                    whileHover={{ scale: 1.02 }}
                                    whileTap={{ scale: 0.98 }}
                                    onClick={handleShowHidden}
                                    title={`Restore ${hiddenIds.length} hidden scan${hiddenIds.length === 1 ? '' : 's'} to this view.`}
                                    className="px-3 py-2 rounded-lg text-xs font-medium text-purple-300 hover:text-white hover:bg-purple-500/10 transition-all flex items-center gap-1.5"
                                >
                                    <span className="material-symbols-outlined text-sm">visibility</span>
                                    Show hidden ({hiddenIds.length})
                                </motion.button>
                            )}
                            <div className="w-[1px] h-4 bg-white/10 self-center mx-1"></div>
                            <motion.button
                                whileHover={{ scale: 1.05 }}
                                whileTap={{ scale: 0.95 }}
                                onClick={() => navigate('newscan')}
                                className="bg-[#8A2BE2] hover:bg-[#7c26cc] text-white px-5 py-2.5 rounded-lg text-sm font-medium flex items-center gap-2 shadow-glow transition-all will-change-transform"
                            >
                                <span className="material-symbols-outlined text-sm">add</span>
                                New Scan
                            </motion.button>
                        </div>
                    </motion.div>

                    <div className="glass-panel-fast rounded-2xl overflow-hidden shadow-glass">
                        <div className="overflow-x-auto">
                            <table className="w-full text-left text-sm whitespace-nowrap glass-table">
                                <thead>
                                    <tr className="border-b border-white/5">
                                        <th className="pl-8 pr-6">Status</th>
                                        <th className="px-6">Scan Name</th>
                                        <th className="px-6">Target Scope</th>
                                        <th className="px-6">Modules</th>
                                        <th className="px-6">Duration</th>
                                        <th className="px-6 pr-8">
                                            <div className="flex items-center gap-1 cursor-pointer hover:text-white transition-colors">
                                                Completed
                                                <span className="material-symbols-outlined text-xs">arrow_downward</span>
                                            </div>
                                        </th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-white/5 text-gray-300">
                                    <AnimatePresence mode='popLayout'>
                                        {visibleScans.length === 0 ? (
                                            <motion.tr
                                                initial={{ opacity: 0 }}
                                                animate={{ opacity: 1 }}
                                                exit={{ opacity: 0 }}
                                            >
                                                <td colSpan="6" className="text-center py-8 text-gray-500">
                                                    {hiddenIds.length > 0
                                                        ? `All ${hiddenIds.length} scan${hiddenIds.length === 1 ? '' : 's'} hidden from view. Use "Show hidden" to restore.`
                                                        : 'No scans recorded. Launch a new scan to see results here.'}
                                                </td>
                                            </motion.tr>
                                        ) : (
                                            visibleScans.map((scan, index) => (
                                                <motion.tr
                                                    key={scan.id}
                                                    initial={{ opacity: 0, y: 10 }}
                                                    animate={{ opacity: 1, y: 0 }}
                                                    transition={{
                                                        duration: 0.3,
                                                        delay: index * 0.05,
                                                        ease: "easeOut"
                                                    }}
                                                    className="hover:bg-white/[0.02] transition-colors group relative"
                                                >
                                                    <td className="pl-8 pr-6 py-5">
                                                        <span className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium border ${scan.status === 'Running'
                                                            ? 'bg-[#1e2338] text-blue-400 border-blue-500/30'
                                                            : scan.status === 'Finalizing'
                                                                ? 'bg-[#251e38] text-purple-400 border-purple-500/30'
                                                                : scan.status === 'Completed' || scan.status === 'Fired'
                                                                    ? 'bg-[#1a2f30] text-teal-400 border-teal-500/30'
                                                                    : 'bg-[#2f1a1a] text-red-400 border-red-500/30'
                                                            }`}>
                                                            <span className={`w-1.5 h-1.5 rounded-full ${scan.status === 'Running' ? 'bg-blue-500 shadow-[0_0_6px_#3b82f6] animate-pulse' :
                                                                scan.status === 'Finalizing' ? 'bg-purple-500 shadow-[0_0_6px_#a855f7] animate-pulse' :
                                                                    scan.status === 'Completed' || scan.status === 'Fired' ? 'bg-teal-400' : 'bg-red-400'
                                                                }`}></span>
                                                            {scan.status}
                                                        </span>
                                                    </td>
                                                    <td className="px-6 py-5 font-medium text-white">{scan.name || "Untitled Scan"}</td>
                                                    <td className="px-6 py-5 text-gray-400 font-mono text-xs tracking-wide truncate max-w-[200px]" title={scan.scope}>
                                                        {scan.scope}
                                                    </td>
                                                    <td className="px-6 py-5">
                                                        <div className="flex gap-1.5">
                                                            <div className="w-7 h-7 rounded bg-[#252038] flex items-center justify-center border border-purple-500/20 group-hover:border-purple-500/40 transition-colors" title="Modules">
                                                                <span className="material-symbols-outlined text-purple-400 text-[14px]">bug_report</span>
                                                            </div>
                                                            {/* Dynamic modules could be here */}
                                                        </div>
                                                    </td>
                                                    <td className="px-6 py-5 text-gray-300 font-mono">
                                                        {scan.status === 'Running' ? (
                                                            <span className="text-blue-300 relative">
                                                                <span className="absolute -left-3 top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full bg-blue-500 animate-ping opacity-75"></span>
                                                                {scan.duration} (Live)
                                                            </span>
                                                        ) : scan.duration}
                                                    </td>
                                                    <td className="px-6 pr-8 py-5">
                                                        <div className="flex items-center justify-between gap-6">
                                                            <span className="text-gray-400 text-xs">{scan.timestamp}</span>
                                                            <motion.button
                                                                whileHover={{ scale: 1.05 }}
                                                                whileTap={{ scale: 0.95 }}
                                                                onClick={() => handleDownloadPdf(scan.id)}
                                                                disabled={(scan.status === 'Running' || !scan.report_ready) || downloading === scan.id}
                                                                title={(scan.status === 'Finalizing' || (scan.status === 'Completed' && !scan.report_ready)) ? "AI is finalizing the forensic report..." : "Download PDF Report"}
                                                                className={`px-3 py-1.5 rounded-md text-[11px] font-medium flex items-center gap-1.5 shadow-[0_0_10px_rgba(138,43,226,0.2)] transition-all ${(scan.status === 'Running' || !scan.report_ready)
                                                                    ? 'bg-gray-700 text-gray-400 cursor-not-allowed opacity-50 shadow-none'
                                                                    : 'bg-[#8A2BE2] text-white hover:bg-[#9d47ff]'
                                                                    } ${downloading === scan.id ? 'opacity-70 cursor-wait' : ''}`}
                                                            >
                                                                <span className={`material-symbols-outlined text-sm ${downloading === scan.id || ((scan.status === 'Finalizing' || (scan.status === 'Completed' && !scan.report_ready))) ? 'animate-spin' : ''}`}>
                                                                    {downloading === scan.id ? 'sync' : ((scan.status === 'Finalizing' || (scan.status === 'Completed' && !scan.report_ready)) ? 'hourglass_empty' : 'download')}
                                                                </span>
                                                                {downloading === scan.id 
                                                                    ? 'Downloading...' 
                                                                    : ((scan.status === 'Finalizing' || (scan.status === 'Completed' && !scan.report_ready)) 
                                                                        ? (progressMap[scan.id] || 'Finalizing AI Report...') 
                                                                        : 'PDF Download')}
                                                            </motion.button>
                                                        </div>
                                                    </td>
                                                </motion.tr>
                                            ))
                                        )}
                                    </AnimatePresence>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </main>

                <footer className="mt-8 pb-8 text-center text-xs text-gray-500 font-light">
                    <p>Vulagent Scanner Intelligence Backbone © 2024</p>
                </footer>
            </div>
        </div>
    );
};

export default Scans;
