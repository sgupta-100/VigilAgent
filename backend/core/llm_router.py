import os
from dataclasses import dataclass, field
from enum import Enum


class ModelTier(str, Enum):
    HIGH = "high"
    MID = "mid"
    LOW = "low"


AGENT_TIERS = {
    "orchestrator": ModelTier.HIGH,
    "alpha": ModelTier.LOW,
    "beta": ModelTier.HIGH,
    "gamma": ModelTier.MID,
    "sigma": ModelTier.MID,
    "omega": ModelTier.HIGH,
    "kappa": ModelTier.LOW,
    "zeta": ModelTier.MID,
    "reporter": ModelTier.MID,
    "recon": ModelTier.LOW,
    "exploit": ModelTier.HIGH,
    "analyst": ModelTier.HIGH,
}

TIER_MODELS = {
    ModelTier.HIGH: ["openai/gpt-5.5", "gemini/gemini-2.5-pro", "anthropic/claude-opus-4-7"],
    ModelTier.MID: ["openai/gpt-5.4", "gemini/gemini-2.5-flash", "anthropic/claude-sonnet-4-6"],
    ModelTier.LOW: ["openai/gpt-5-nano", "gemini/gemini-2.5-flash-lite", "anthropic/claude-haiku-4-5"],
}

AGENT_TEMPERATURES = {
    "orchestrator": 0.3,
    "alpha": 0.3,
    "beta": 0.2,
    "gamma": 0.2,
    "sigma": 0.2,
    "omega": 0.3,
    "kappa": 0.2,
    "zeta": 0.2,
    "reporter": 0.5,
}


@dataclass
class ModelAssignment:
    primary: str
    fallbacks: list[str] = field(default_factory=list)
    temperature: float = 0.3
    tier: ModelTier = ModelTier.MID


class LLMRouter:
    def __init__(self, profile: str | None = None):
        self.profile = (profile or os.getenv("ANTIGRAVITY_MODEL_PROFILE", "eco")).lower()

    def tier_for(self, agent_name: str) -> ModelTier:
        if self.profile == "max":
            return ModelTier.HIGH
        if self.profile in {"test", "ci"}:
            return ModelTier.LOW
        key = agent_name.lower().replace("agent_", "")
        return AGENT_TIERS.get(key, ModelTier.MID)

    def resolve(self, agent_name: str) -> ModelAssignment:
        env_key = f"ANTIGRAVITY_{agent_name.upper().replace('AGENT_', '')}_MODEL"
        override = os.getenv(env_key) or os.getenv("ANTIGRAVITY_MODEL")
        tier = self.tier_for(agent_name)
        chain = [override] if override else list(TIER_MODELS[tier])
        return ModelAssignment(
            primary=chain[0],
            fallbacks=chain[1:],
            temperature=AGENT_TEMPERATURES.get(agent_name.lower().replace("agent_", ""), 0.3),
            tier=tier,
        )


llm_router = LLMRouter()
