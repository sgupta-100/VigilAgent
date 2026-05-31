import React from 'react';

/**
 * SeverityBadge — pill-style severity indicator.
 *
 * Uses the canonical report color tokens so badge color matches generated PDFs:
 *   CRITICAL = #C0392B   HIGH = #E67E22   MEDIUM = #F1C40F   LOW = #27AE60
 *
 * @typedef {Object} SeverityBadgeProps
 * @property {'CRITICAL'|'HIGH'|'MEDIUM'|'LOW'|'INFO'|string} severity
 * @property {'sm'|'md'} [size]      Default 'sm'.
 * @property {string}    [className]
 *
 * @param {SeverityBadgeProps} props
 */
const SEVERITY_STYLES = {
    CRITICAL: { bg: 'bg-[#C0392B]', text: 'text-white' },
    HIGH:     { bg: 'bg-[#E67E22]', text: 'text-black' },
    MEDIUM:   { bg: 'bg-[#F1C40F]', text: 'text-black' },
    LOW:      { bg: 'bg-[#27AE60]', text: 'text-black' },
    INFO:     { bg: 'bg-[#3498DB]', text: 'text-white' },
};

const SIZE_CLASSES = {
    sm: 'px-2 py-0.5 text-[10px]',
    md: 'px-2.5 py-1 text-xs',
};

function SeverityBadge({ severity, size = 'sm', className = '' }) {
    const upper = (severity || 'INFO').toUpperCase();
    const style = SEVERITY_STYLES[upper] || SEVERITY_STYLES.INFO;
    const sizeCls = SIZE_CLASSES[size] || SIZE_CLASSES.sm;

    return (
        <span
            role="status"
            aria-label={`Severity: ${upper}`}
            className={`
                inline-flex items-center justify-center
                rounded font-bold tracking-wide uppercase
                ${style.bg} ${style.text} ${sizeCls} ${className}
            `}
        >
            {upper}
        </span>
    );
}

export default React.memo(SeverityBadge);
