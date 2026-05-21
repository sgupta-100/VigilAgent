/**
 * Shared agent-name-to-display-name mapping.
 * Used by dashboard and live monitoring views.
 */

const AGENT_MAP = [
    { match: 'theta',       name: 'THE SENTINEL',      color: 'text-purple-400' },
    { match: 'iota',        name: 'THE INSPECTOR',     color: 'text-orange-400' },
    { match: 'beta',        name: 'BETA (BREAKER)',    color: 'text-red-400' },
    { match: 'alpha_recon', name: 'ALPHA (RECON)',     color: 'text-cyan-400' },
    { match: 'alpha',       name: 'ALPHA (SCOUT)',     color: 'text-cyan-400' },
    { match: 'gamma',       name: 'GAMMA (TYCOON)',    color: 'text-yellow-400' },
    { match: 'omega',       name: 'OMEGA (STRAT)',     color: 'text-pink-400' },
    { match: 'zeta',        name: 'ZETA (CORTEX)',     color: 'text-indigo-400' },
    { match: 'sigma',       name: 'SIGMA (SMITH)',     color: 'text-green-400' },
    { match: 'kappa',       name: 'KAPPA (LIBRARIAN)', color: 'text-teal-400' },
    { match: 'planner',     name: 'PLANNER',           color: 'text-amber-400' },
    { match: 'Orchestrator',name: 'ORCHESTRATOR',      color: 'text-fuchsia-400' },
    { match: 'spy',         name: 'SPY',               color: 'text-slate-400' },
    { match: 'synapse',     name: 'SYNAPSE',           color: 'text-sky-400' },
];

/**
 * Resolve an agent identifier string to a display name + tailwind color class.
 * @param {string} agentId - e.g. "agent_beta", "alpha_recon", "Orchestrator"
 * @returns {{ name: string, color: string }}
 */
export function resolveAgent(agentId) {
    if (!agentId) return { name: 'UNKNOWN', color: 'text-gray-400' };
    for (const entry of AGENT_MAP) {
        if (agentId.includes(entry.match)) {
            return { name: entry.name, color: entry.color };
        }
    }
    return { name: 'UNKNOWN', color: 'text-gray-400' };
}
