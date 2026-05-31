import React from 'react';

/**
 * Spinner — accessible CSS-only busy indicator.
 *
 * @typedef {Object} SpinnerProps
 * @property {'sm'|'md'|'lg'} [size]      Visual size. Defaults to 'md'.
 * @property {string}         [label]     Screen-reader label. Defaults to 'Loading'.
 * @property {string}         [className] Extra classes.
 * @property {string}         [color]     Tailwind text color class (controls stroke). Defaults to 'text-[#9b61ff]'.
 *
 * @param {SpinnerProps} props
 */
const SIZE_MAP = {
    sm: 'w-3.5 h-3.5 border-[2px]',
    md: 'w-5 h-5 border-[2px]',
    lg: 'w-8 h-8 border-[3px]',
};

function Spinner({ size = 'md', label = 'Loading', className = '', color = 'text-[#9b61ff]' }) {
    const sizeClasses = SIZE_MAP[size] || SIZE_MAP.md;

    return (
        <span
            role="status"
            aria-live="polite"
            aria-label={label}
            className={`inline-flex items-center justify-center ${className}`}
        >
            <span
                aria-hidden="true"
                className={`
                    ${sizeClasses} ${color}
                    inline-block rounded-full
                    border-current border-r-transparent
                    animate-spin
                    motion-reduce:animate-[spin_1.5s_linear_infinite]
                `}
            />
            <span className="sr-only">{label}</span>
        </span>
    );
}

export default Spinner;
