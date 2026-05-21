import React from 'react';

/**
 * Production-grade React Error Boundary.
 * Prevents full white-screen crashes by catching render errors
 * and showing a recovery UI instead.
 */
class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        console.error('[ErrorBoundary] Caught render error:', error, errorInfo);
    }

    handleReset = () => {
        this.setState({ hasError: false, error: null });
    };

    render() {
        if (this.state.hasError) {
            return (
                <div
                    style={{
                        minHeight: '100vh',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        background: '#06070B',
                        fontFamily: "'Inter', sans-serif",
                        color: '#e2e8f0',
                    }}
                >
                    <div style={{ textAlign: 'center', maxWidth: 420, padding: 32 }}>
                        <div
                            style={{
                                width: 64,
                                height: 64,
                                borderRadius: '50%',
                                background: 'rgba(239,68,68,0.1)',
                                border: '1px solid rgba(239,68,68,0.3)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                margin: '0 auto 24px',
                            }}
                        >
                            <span className="material-icons" style={{ color: '#f87171', fontSize: 32 }}>
                                error_outline
                            </span>
                        </div>
                        <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 8 }}>
                            Something went wrong
                        </h2>
                        <p style={{ fontSize: 14, color: '#94a3b8', marginBottom: 24, lineHeight: 1.6 }}>
                            An unexpected error occurred in the UI. Your data is safe.
                        </p>
                        <button
                            onClick={this.handleReset}
                            style={{
                                background: '#8A2BE2',
                                color: '#fff',
                                border: 'none',
                                padding: '10px 24px',
                                borderRadius: 8,
                                fontSize: 14,
                                fontWeight: 500,
                                cursor: 'pointer',
                            }}
                        >
                            Try Again
                        </button>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
