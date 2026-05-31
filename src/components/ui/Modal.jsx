import React, { useCallback, useEffect, useRef } from 'react';

/**
 * Modal — accessible dialog with focus trap, ESC-to-close, and backdrop dismiss.
 *
 * @typedef {Object} ModalProps
 * @property {boolean}                open                     Controls visibility.
 * @property {() => void}             onClose                  Fires on ESC, backdrop click, or close button.
 * @property {string}                 [title]                  Optional title (also used for aria-labelledby).
 * @property {React.ReactNode}        [description]            Optional supporting copy beneath the title.
 * @property {React.ReactNode}        children                 Body content.
 * @property {React.ReactNode}        [footer]                 Optional sticky footer (typically action buttons).
 * @property {'sm'|'md'|'lg'|'xl'}    [size]                   Width preset. Default 'md'.
 * @property {boolean}                [closeOnBackdrop]        Default true.
 * @property {boolean}                [closeOnEsc]             Default true.
 * @property {boolean}                [showCloseButton]        Default true.
 * @property {string}                 [className]              Extra classes on the panel.
 * @property {string}                 [ariaLabel]              Use when no `title` is provided.
 *
 * @param {ModalProps} props
 */

const SIZE_CLASSES = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-2xl',
    xl: 'max-w-4xl',
};

const FOCUSABLE_SELECTOR =
    'a[href], area[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), ' +
    'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function Modal({
    open,
    onClose,
    title,
    description,
    children,
    footer,
    size = 'md',
    closeOnBackdrop = true,
    closeOnEsc = true,
    showCloseButton = true,
    className = '',
    ariaLabel,
}) {
    const panelRef = useRef(null);
    const previouslyFocusedRef = useRef(null);
    const titleId = useRef(`modal-title-${Math.random().toString(36).slice(2, 9)}`).current;
    const descId = useRef(`modal-desc-${Math.random().toString(36).slice(2, 9)}`).current;

    // Track previously focused element when opening; restore it on close.
    useEffect(() => {
        if (!open) return;

        previouslyFocusedRef.current = document.activeElement instanceof HTMLElement
            ? document.activeElement
            : null;

        // Focus the first focusable inside the panel (or the panel itself).
        const focusFirst = () => {
            const panel = panelRef.current;
            if (!panel) return;
            const focusables = panel.querySelectorAll(FOCUSABLE_SELECTOR);
            const first = focusables[0];
            if (first instanceof HTMLElement) {
                first.focus();
            } else {
                panel.focus();
            }
        };

        // requestAnimationFrame ensures DOM has painted before we focus.
        const raf = requestAnimationFrame(focusFirst);

        return () => {
            cancelAnimationFrame(raf);
            const prev = previouslyFocusedRef.current;
            if (prev && document.contains(prev)) {
                prev.focus();
            }
        };
    }, [open]);

    // ESC + Tab focus trap
    const handleKeyDown = useCallback(
        (e) => {
            if (!open) return;

            if (e.key === 'Escape' && closeOnEsc) {
                e.stopPropagation();
                onClose?.();
                return;
            }

            if (e.key === 'Tab' && panelRef.current) {
                const focusables = Array.from(
                    panelRef.current.querySelectorAll(FOCUSABLE_SELECTOR)
                ).filter((el) => el instanceof HTMLElement && !el.hasAttribute('disabled'));

                if (focusables.length === 0) {
                    e.preventDefault();
                    panelRef.current.focus();
                    return;
                }

                const first = focusables[0];
                const last = focusables[focusables.length - 1];
                const active = document.activeElement;

                if (e.shiftKey && active === first) {
                    e.preventDefault();
                    last.focus();
                } else if (!e.shiftKey && active === last) {
                    e.preventDefault();
                    first.focus();
                }
            }
        },
        [open, closeOnEsc, onClose]
    );

    // Lock scroll while open.
    useEffect(() => {
        if (!open) return;
        const original = document.body.style.overflow;
        document.body.style.overflow = 'hidden';
        return () => {
            document.body.style.overflow = original;
        };
    }, [open]);

    if (!open) return null;

    const handleBackdropMouseDown = (e) => {
        // Only treat as backdrop click if mousedown started on backdrop itself.
        if (closeOnBackdrop && e.target === e.currentTarget) {
            onClose?.();
        }
    };

    return (
        <div
            className="fixed inset-0 z-[1000] flex items-center justify-center px-4 py-6 bg-black/70 backdrop-blur-sm animate-[modalFade_140ms_ease-out] motion-reduce:animate-none"
            onMouseDown={handleBackdropMouseDown}
            onKeyDown={handleKeyDown}
        >
            <div
                ref={panelRef}
                role="dialog"
                aria-modal="true"
                aria-labelledby={title ? titleId : undefined}
                aria-describedby={description ? descId : undefined}
                aria-label={!title ? ariaLabel : undefined}
                tabIndex={-1}
                className={`
                    relative w-full ${SIZE_CLASSES[size] || SIZE_CLASSES.md}
                    bg-[#3E425E]/95 backdrop-blur-xl
                    border border-white/10 rounded-xl shadow-[0_24px_60px_rgba(0,0,0,0.6)]
                    flex flex-col max-h-[90vh] outline-none
                    animate-[modalIn_160ms_ease-out] motion-reduce:animate-none
                    ${className}
                `}
            >
                {(title || showCloseButton) && (
                    <div className="flex items-start justify-between gap-4 px-6 pt-5 pb-3 border-b border-white/5">
                        <div className="flex-1 min-w-0">
                            {title && (
                                <h2
                                    id={titleId}
                                    className="text-lg font-semibold text-white leading-tight"
                                >
                                    {title}
                                </h2>
                            )}
                            {description && (
                                <p id={descId} className="mt-1 text-xs text-gray-400 leading-relaxed">
                                    {description}
                                </p>
                            )}
                        </div>
                        {showCloseButton && (
                            <button
                                type="button"
                                onClick={onClose}
                                aria-label="Close dialog"
                                className="
                                    flex-shrink-0 -mt-1 -mr-2 p-2 rounded-md
                                    text-gray-400 hover:text-white hover:bg-white/5
                                    transition-colors
                                    focus:outline-none focus-visible:ring-2 focus-visible:ring-[#9b61ff]
                                "
                            >
                                <span className="material-symbols-outlined text-lg" aria-hidden="true">close</span>
                            </button>
                        )}
                    </div>
                )}

                <div className="flex-1 overflow-y-auto px-6 py-4 text-sm text-gray-200">
                    {children}
                </div>

                {footer && (
                    <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-white/5">
                        {footer}
                    </div>
                )}
            </div>

            <style>{`
                @keyframes modalFade {
                    from { opacity: 0; }
                    to   { opacity: 1; }
                }
                @keyframes modalIn {
                    from { opacity: 0; transform: translateY(8px) scale(0.98); }
                    to   { opacity: 1; transform: translateY(0)   scale(1);    }
                }
            `}</style>
        </div>
    );
}

export default Modal;
