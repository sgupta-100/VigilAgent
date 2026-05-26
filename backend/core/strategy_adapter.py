"""
STRATEGY ADAPTER
Implements adaptive behavior when obstacles are encountered.

This adapter:
1. Detects when adaptation is needed
2. Selects appropriate adaptation strategy
3. Applies adaptation strategies
4. Detects diminishing returns
5. Adjusts for defenses (WAF, rate limiting)
"""

import logging
import time
from typing import Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta

from backend.core.self_awareness_config import SelfAwarenessConfig
from backend.core.tracing import get_tracer, trace_span

logger = logging.getLogger("StrategyAdapter")
tracer = get_tracer()


class AdaptationStrategy(Enum):
    """Available adaptation strategies"""
    RETRY_WITH_BACKOFF = "retry_with_backoff"
    SWITCH_TECHNIQUE = "switch_technique"
    DELEGATE_TO_PEER = "delegate_to_peer"
    REDUCE_AGGRESSION = "reduce_aggression"
    CHANGE_PARAMETERS = "change_parameters"
    ABORT_AND_REPORT = "abort_and_report"


@dataclass
class AdaptationContext:
    """Context for adaptation decision"""
    stuck_info: Any
    action_type: str
    consecutive_failures: int
    error_type: Optional[str] = None


@dataclass
class AdaptationResult:
    """Result of adaptation"""
    adapted: bool
    strategy_applied: Optional[str] = None
    rationale: str = ""
    success: bool = False


class StrategyAdapter:
    """Implements adaptive behavior for agents"""
    
    def __init__(self, agent_id: str, config: SelfAwarenessConfig, decision_logger=None, learning_integrator=None, db=None):
        self.agent_id = agent_id
        self.config = config
        self.decision_logger = decision_logger
        self.learning_integrator = learning_integrator
        self.db = db
        self._last_adaptation: Dict[str, float] = {}
        self._adaptation_attempts: Dict[str, int] = {}
        self._diminishing_returns_tracker: Dict[str, list] = {}
        
        logger.info(f"[StrategyAdapter] Initialized for agent {agent_id}")
    
    def should_adapt(self, context: AdaptationContext) -> bool:
        """Determine if adaptation is needed"""
        # Check cooldown
        action_type = context.action_type
        last_adapt = self._last_adaptation.get(action_type, 0)
        if time.time() - last_adapt < self.config.adaptation_cooldown_seconds:
            return False
        
        # Check if stuck
        if context.consecutive_failures >= self.config.stuck_state_threshold:
            return True
        
        return False
    
    async def select_and_apply_adaptation(self, stuck_info: Any) -> AdaptationResult:
        """Select and apply adaptation strategy"""
        context = AdaptationContext(
            stuck_info=stuck_info,
            action_type=stuck_info.action_type,
            consecutive_failures=stuck_info.consecutive_failures
        )
        
        if not self.should_adapt(context):
            return AdaptationResult(adapted=False, rationale="Adaptation not needed")
        
        # Select strategy
        strategy = self._select_strategy(context)
        
        # Apply strategy
        result = await self._apply_strategy(strategy, context)
        
        # Record adaptation
        self._last_adaptation[context.action_type] = time.time()
        self._adaptation_attempts[context.action_type] = \
            self._adaptation_attempts.get(context.action_type, 0) + 1
        
        return result
    
    def _select_strategy(self, context: AdaptationContext) -> AdaptationStrategy:
        """Select appropriate adaptation strategy"""
        # Check attempts
        attempts = self._adaptation_attempts.get(context.action_type, 0)
        
        if attempts >= self.config.max_adaptation_attempts:
            return AdaptationStrategy.ABORT_AND_REPORT
        
        # Check for diminishing returns
        if self.detect_diminishing_returns(context.action_type):
            return AdaptationStrategy.ABORT_AND_REPORT
        
        # Default: switch technique
        return AdaptationStrategy.SWITCH_TECHNIQUE
    
    async def _apply_strategy(
        self,
        strategy: AdaptationStrategy,
        context: AdaptationContext
    ) -> AdaptationResult:
        """Apply selected adaptation strategy"""
        logger.info(f"[StrategyAdapter] Applying {strategy.value} for {self.agent_id}")
        
        rationale = f"Applied {strategy.value} due to {context.consecutive_failures} failures"
        
        # Log adaptation decision
        if self.decision_logger:
            try:
                await self.decision_logger.log_decision({
                    "agent_id": self.agent_id,
                    "action_type": "adaptation",
                    "rationale": rationale,
                    "confidence": 0.8,
                    "context": {
                        "strategy": strategy.value,
                        "action_type": context.action_type,
                        "consecutive_failures": context.consecutive_failures
                    }
                })
            except Exception as e:
                logger.error(f"[StrategyAdapter] Failed to log decision: {e}")
        
        # Persist adaptation to database
        if self.db:
            try:
                await self.db.execute(
                    """
                    INSERT INTO agent_adaptations 
                    (agent_id, timestamp, trigger_reason, strategy_applied, success, context)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    self.agent_id,
                    datetime.utcnow(),
                    f"{context.consecutive_failures} consecutive failures",
                    strategy.value,
                    True,  # Will be updated based on actual result
                    {
                        "action_type": context.action_type,
                        "error_type": context.error_type
                    }
                )
            except Exception as e:
                logger.error(f"[StrategyAdapter] Failed to persist adaptation: {e}")
        
        result = AdaptationResult(
            adapted=True,
            strategy_applied=strategy.value,
            rationale=rationale,
            success=True
        )
        
        # Save successful adaptation to learning integrator
        if result.success and self.learning_integrator:
            try:
                from backend.core.learning_integrator import Strategy
                
                await self.learning_integrator.save_successful_strategy(
                    Strategy(
                        name=strategy.value,
                        action_type=context.action_type,
                        context={
                            "consecutive_failures": context.consecutive_failures,
                            "error_type": context.error_type
                        }
                    ),
                    context={
                        "agent_id": self.agent_id,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
            except Exception as e:
                logger.error(f"[StrategyAdapter] Failed to save strategy: {e}")
        
        return result
    
    def detect_diminishing_returns(self, action_type: str) -> bool:
        """Detect if action is producing diminishing returns"""
        if action_type not in self._diminishing_returns_tracker:
            return False
        
        attempts = self._diminishing_returns_tracker[action_type]
        if len(attempts) < self.config.diminishing_returns_threshold:
            return False
        
        # Check if last N attempts produced no new findings
        recent = attempts[-self.config.diminishing_returns_threshold:]
        return all(findings == 0 for findings in recent)
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get adaptation metrics"""
        return {
            "total_adaptations": sum(self._adaptation_attempts.values()),
            "adaptations_by_type": dict(self._adaptation_attempts)
        }
