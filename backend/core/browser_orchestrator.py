"""
Compatibility shim for browser_orchestrator.py
Re-exports from browser_engine.py (Scrappling) for backward compatibility.
"""

from backend.core.browser_engine import (
    BrowserEngine,
    BrowserOrchestrator,
    ScrapplingUnavailable as BrowserUnavailable,
    OpenClawEngine,
    PinchTabEngine,
    PinchTabInstance,
    PinchTabClient,
    get_browser_orchestrator,
    ScrapplingEngine,
)

# Re-export all public API
__all__ = [
    "BrowserEngine",
    "BrowserOrchestrator", 
    "BrowserUnavailable",
    "OpenClawEngine",
    "PinchTabEngine",
    "PinchTabInstance",
    "PinchTabClient",
    "get_browser_orchestrator",
    "ScrapplingEngine",
]