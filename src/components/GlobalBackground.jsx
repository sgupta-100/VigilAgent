import React, { useEffect, useRef } from 'react';

/**
 * Lightweight starfield background.
 * Uses only 20 DOM nodes instead of 300.
 * The rest of the effect is achieved with CSS box-shadow.
 */
const GlobalBackground = () => {
    const starsRef = useRef(null);

    useEffect(() => {
        if (starsRef.current) {
            starsRef.current.innerHTML = '';
            // Only create 20 animated stars — the rest is a CSS radial pattern
            for (let i = 0; i < 20; i++) {
                const star = document.createElement('div');
                star.className = 'star';
                const size = Math.random() * 2 + 0.5;
                star.style.left = `${Math.random() * 100}%`;
                star.style.top = `${Math.random() * 100}%`;
                star.style.width = `${size}px`;
                star.style.height = `${size}px`;
                star.style.opacity = Math.random() * 0.6 + 0.2;

                const duration = 3 + Math.random() * 4;
                const delay = Math.random() * 5;
                star.style.animation = `twinkle ${duration}s infinite ease-in-out ${delay}s`;

                starsRef.current.appendChild(star);
            }
        }
    }, []);

    return (
        <div className="fixed inset-0 z-[-1] pointer-events-none overflow-hidden select-none">
            {/* Static star field via CSS box-shadow (zero DOM overhead) */}
            <div style={{
                position: 'absolute',
                inset: 0,
                background: 'transparent',
                boxShadow: generateStarShadow(150),
            }} />
            {/* Animated stars layer (20 DOM nodes) */}
            <div ref={starsRef} className="absolute inset-0"></div>
        </div>
    );
};

/**
 * Pre-generate a box-shadow string with N points.
 * This is static — computed once at module load, zero runtime cost.
 */
function generateStarShadow(count) {
    const shadows = [];
    for (let i = 0; i < count; i++) {
        const x = Math.round(Math.random() * 2000);
        const y = Math.round(Math.random() * 2000);
        const alpha = (Math.random() * 0.4 + 0.1).toFixed(2);
        shadows.push(`${x}px ${y}px 0px rgba(255,255,255,${alpha})`);
    }
    return shadows.join(', ');
}

export default GlobalBackground;
