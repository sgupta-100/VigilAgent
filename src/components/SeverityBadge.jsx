import React from 'react';

/**
 * Reusable severity badge component.
 * Eliminates duplicated badge logic across scan and report views.
 *
 * @param {{ severity: string, className?: string }} props
 */
const SEVERITY_STYLES = {
    CRITICAL: 'bg-red-500 text-black',
    HIGH:     'bg-orange-500 text-black',
    MEDIUM:   'bg-yellow-500 text-black',
    LOW:      'bg-green-500 text-black',
    INFO:     'bg-blue-500 text-black',
};

function SeverityBadge({ severity, className = '' }) {
    const upper = (severity || 'INFO').toUpperCase();
    const style = SEVERITY_STYLES[upper] || SEVERITY_STYLES.INFO;

    return (
        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${style} ${className}`}>
            {upper}
        </span>
    );
}

export default React.memo(SeverityBadge);
