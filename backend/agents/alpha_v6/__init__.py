"""Alpha V6 Deep Reconnaissance Engine.

Exports:
    AlphaV6ReconOrchestrator — Alias for AlphaOrchestrator (backward compat)
    AlphaV6DeepOrchestrator  — Alias for AlphaOrchestrator (backward compat)
    recon_router             — FastAPI router for recon API
"""
__all__ = [
    "AlphaOrchestrator",
    "AlphaV6ReconOrchestrator",
    "AlphaV6DeepOrchestrator",
    "recon_router",
]


def __getattr__(name: str):
    if name in ("AlphaOrchestrator", "AlphaV6ReconOrchestrator", "AlphaV6DeepOrchestrator"):
        from backend.agents.alpha_v6.alpha_orchestrator import AlphaOrchestrator
        return AlphaOrchestrator
    if name == "recon_router":
        from backend.agents.alpha_v6.api_routes import router
        return router
    raise AttributeError(name)
