import { ReactLenis } from 'lenis/react';
import { useEffect, useState } from 'react';

/**
 * SmoothScroll — wraps the app in Lenis for smooth wheel/touch scrolling.
 *
 * Accessibility notes:
 *   - smoothWheel: true   → intercepts mouse wheel and trackpad scrolling.
 *   - Lenis does NOT intercept keyboard scroll keys (Arrow, PgUp/PgDn,
 *     Home/End, Space). Browsers handle those natively, so keyboard users
 *     keep full scroll control with no extra config required.
 *   - We respect prefers-reduced-motion: when set, Lenis is disabled and the
 *     browser's default scroll is used.
 */
const SmoothScroll = ({ children }) => {
    const [reduceMotion, setReduceMotion] = useState(false);

    useEffect(() => {
        if (typeof window === 'undefined' || !window.matchMedia) return;
        const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
        const onChange = () => setReduceMotion(mq.matches);
        onChange();
        // Safari < 14 needs addListener
        if (mq.addEventListener) mq.addEventListener('change', onChange);
        else mq.addListener(onChange);
        return () => {
            if (mq.removeEventListener) mq.removeEventListener('change', onChange);
            else mq.removeListener(onChange);
        };
    }, []);

    if (reduceMotion) {
        // Bypass Lenis entirely — native scroll is the more accessible default.
        return <>{children}</>;
    }

    return (
        <ReactLenis
            root
            options={{
                lerp: 0.1,
                duration: 1.2,
                smoothWheel: true,
                // Keyboard scrolling is left to the browser — do not override.
            }}
        >
            {children}
        </ReactLenis>
    );
};

export default SmoothScroll;
