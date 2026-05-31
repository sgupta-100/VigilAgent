import React from 'react';
import Button from './Button';

/**
 * EmptyState — friendly placeholder for empty / errored / unauthorized views.
 *
 * @typedef {Object} EmptyStateProps
 * @property {string}            [icon]        material-symbols glyph name. Default 'inbox'.
 * @property {string}            title         Headline text.
 * @property {string}            [description] Optional supporting copy.
 * @property {Object}            [action]      Optional CTA. Renders a primary <Button>.
 * @property {string}            action.label
 * @property {() => void}        action.onClick
 * @property {string}            [action.icon] Optional material-symbol prefix on the CTA.
 * @property {React.ReactNode}   [secondaryAction] Optional additional element (e.g. ghost button).
 * @property {'sm'|'md'|'lg'}    [size]        Visual scale. Default 'md'.
 * @property {string}            [className]
 *
 * @param {EmptyStateProps} props
 */

const SIZE = {
    sm: { wrap: 'py-8',  glyph: 'text-3xl', glyphBox: 'w-12 h-12', title: 'text-base',  desc: 'text-xs'  },
    md: { wrap: 'py-12', glyph: 'text-4xl', glyphBox: 'w-16 h-16', title: 'text-lg',    desc: 'text-sm'  },
    lg: { wrap: 'py-16', glyph: 'text-5xl', glyphBox: 'w-20 h-20', title: 'text-xl',    desc: 'text-base'},
};

function EmptyState({
    icon = 'inbox',
    title,
    description,
    action,
    secondaryAction,
    size = 'md',
    className = '',
}) {
    const s = SIZE[size] || SIZE.md;

    return (
        <div
            role="region"
            aria-label={title}
            className={`
                w-full flex flex-col items-center justify-center text-center
                px-4 ${s.wrap} ${className}
            `}
        >
            <div
                aria-hidden="true"
                className={`
                    ${s.glyphBox}
                    rounded-full bg-[#9b61ff]/10 border border-[#9b61ff]/25
                    flex items-center justify-center mb-4
                    shadow-[0_0_24px_rgba(155,97,255,0.15)]
                `}
            >
                <span className={`material-symbols-outlined ${s.glyph} text-[#9b61ff]`}>
                    {icon}
                </span>
            </div>

            <h3 className={`${s.title} font-semibold text-white mb-1.5`}>{title}</h3>

            {description && (
                <p className={`${s.desc} text-gray-400 max-w-sm leading-relaxed mb-5`}>
                    {description}
                </p>
            )}

            {(action || secondaryAction) && (
                <div className="flex flex-col sm:flex-row items-center gap-2 mt-1">
                    {action && (
                        <Button
                            variant="primary"
                            size={size === 'lg' ? 'md' : 'sm'}
                            onClick={action.onClick}
                            icon={
                                action.icon ? (
                                    <span className="material-symbols-outlined text-base">
                                        {action.icon}
                                    </span>
                                ) : undefined
                            }
                        >
                            {action.label}
                        </Button>
                    )}
                    {secondaryAction}
                </div>
            )}
        </div>
    );
}

export default EmptyState;
