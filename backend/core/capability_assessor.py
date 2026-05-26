"""
CAPABILITY ASSESSOR
Maintains and evaluates agent skill proficiency.

This assessor:
1. Tracks proficiency scores for each skill (0.0 to 1.0)
2. Updates proficiency using exponential moving average
3. Evaluates task suitability based on proficiency
4. Checks prerequisites for actions
5. Suggests delegation for low proficiency tasks
"""

import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from backend.core.self_awareness_config import SelfAwarenessConfig
from backend.core.database import db_manager
from backend.core.tracing import get_tracer, trace_span

logger = logging.getLogger("CapabilityAssessor")
tracer = get_tracer()


@dataclass
class PrerequisiteCheck:
    """Result of prerequisite verification"""
    satisfied: bool
    missing_prerequisites: list
    rationale: str


class CapabilityAssessor:
    """
    Maintains and evaluates agent skill proficiency.
    
    Features:
    - Proficiency score tracking (0.0 to 1.0)
    - Exponential moving average updates
    - Task suitability evaluation
    - Prerequisite checking
    - Delegation suggestions
    """
    
    def __init__(
        self,
        agent_id: str,
        config: SelfAwarenessConfig
    ):
        """
        Initialize capability assessor.
        
        Args:
            agent_id: ID of the agent
            config: Self-awareness configuration
        """
        self.agent_id = agent_id
        self.config = config
        
        # In-memory proficiency map
        self._proficiency_scores: Dict[str, float] = {}
        self._attempt_counts: Dict[str, int] = {}
        self._success_counts: Dict[str, int] = {}
        
        # Load from database
        self._loaded = False
        
        logger.info(f"[CapabilityAssessor] Initialized for agent {agent_id}")
    
    async def _ensure_loaded(self):
        """Ensure proficiency scores are loaded from database"""
        if self._loaded:
            return
        
        try:
            await self._load_from_db()
            self._loaded = True
        except Exception as e:
            logger.error(f"[CapabilityAssessor] Failed to load from database: {e}")
    
    async def get_proficiency(self, skill: str) -> float:
        """
        Get proficiency score for a skill.
        
        Args:
            skill: Name of the skill
            
        Returns:
            Proficiency score (0.0 to 1.0)
        """
        await self._ensure_loaded()
        
        return self._proficiency_scores.get(
            skill,
            self.config.initial_proficiency
        )
    
    async def update_proficiency(
        self,
        skill: str,
        outcome: bool,
        context: Dict[str, Any]
    ) -> None:
        """
        Update proficiency based on action outcome.
        
        Uses exponential moving average:
        - Success: score += (1.0 - score) * learning_rate
        - Failure: score -= score * learning_rate
        
        Args:
            skill: Name of the skill
            outcome: True if successful, False if failed
            context: Additional context about the action
        """
        with trace_span(
            "capability_assessor.update_proficiency",
            {
                "agent_id": self.agent_id,
                "skill": skill,
                "outcome": outcome
            }
        ) as span:
            await self._ensure_loaded()
            
            # Get current score
            current_score = await self.get_proficiency(skill)
            
            # Update using exponential moving average
            learning_rate = self.config.proficiency_learning_rate
            
            if outcome:
                new_score = current_score + (1.0 - current_score) * learning_rate
                self._success_counts[skill] = self._success_counts.get(skill, 0) + 1
            else:
                new_score = current_score - current_score * learning_rate
            
            # Ensure bounds [0.0, 1.0]
            new_score = max(0.0, min(1.0, new_score))
            
            # Update in-memory
            self._proficiency_scores[skill] = new_score
            self._attempt_counts[skill] = self._attempt_counts.get(skill, 0) + 1
            
            # Add metrics to span
            if span:
                span.set_attribute("old_score", current_score)
                span.set_attribute("new_score", new_score)
                span.set_attribute("total_attempts", self._attempt_counts[skill])
            
            # Persist to database
            await self._save_to_db(skill, new_score)
            
            logger.debug(
                f"[CapabilityAssessor] Updated {skill} proficiency: "
                f"{current_score:.3f} -> {new_score:.3f} (outcome={outcome})"
            )
    
    async def can_perform(
        self,
        skill: str,
        min_proficiency: Optional[float] = None
    ) -> bool:
        """
        Check if agent can perform skill at required level.
        
        Args:
            skill: Name of the skill
            min_proficiency: Minimum required proficiency (uses config default if None)
            
        Returns:
            True if agent can perform, False otherwise
        """
        if min_proficiency is None:
            min_proficiency = self.config.min_proficiency_for_task
        
        proficiency = await self.get_proficiency(skill)
        return proficiency >= min_proficiency
    
    async def check_prerequisites(
        self,
        action: Any,
        context: Dict[str, Any]
    ) -> PrerequisiteCheck:
        """
        Verify prerequisites for action are satisfied.
        
        Args:
            action: The action to check
            context: Current execution context
            
        Returns:
            PrerequisiteCheck with verification results
        """
        # Extract prerequisites from action
        prerequisites = getattr(action, 'prerequisites', [])
        
        if not prerequisites:
            return PrerequisiteCheck(
                satisfied=True,
                missing_prerequisites=[],
                rationale="No prerequisites required"
            )
        
        # Check each prerequisite
        missing = []
        for prereq in prerequisites:
            # Check if prerequisite is satisfied in context
            if prereq not in context or not context[prereq]:
                missing.append(prereq)
        
        satisfied = len(missing) == 0
        
        return PrerequisiteCheck(
            satisfied=satisfied,
            missing_prerequisites=missing,
            rationale=f"Missing prerequisites: {missing}" if missing else "All prerequisites satisfied"
        )
    
    async def get_skill_map(self) -> Dict[str, float]:
        """
        Get complete skill proficiency map.
        
        Returns:
            Dictionary mapping skill names to proficiency scores
        """
        await self._ensure_loaded()
        return self._proficiency_scores.copy()
    
    async def suggest_delegation(self, skill: str) -> Optional[str]:
        """
        Suggest better agent for skill if current proficiency is low.
        
        Args:
            skill: Name of the skill
            
        Returns:
            Suggested agent ID or None
        """
        proficiency = await self.get_proficiency(skill)
        
        if proficiency >= self.config.min_proficiency_for_task:
            return None  # Current agent is capable
        
        # Query database for agents with higher proficiency
        try:
            await db_manager.initialize()
            
            query = """
                SELECT agent_id, proficiency_score
                FROM agent_proficiency
                WHERE skill = $1
                AND proficiency_score > $2
                ORDER BY proficiency_score DESC
                LIMIT 1
            """
            
            async with db_manager.pool.acquire() as conn:
                row = await conn.fetchrow(query, skill, proficiency)
                
                if row:
                    return row['agent_id']
            
        except Exception as e:
            logger.error(f"[CapabilityAssessor] Failed to query for delegation: {e}")
        
        return None
    
    async def _load_from_db(self):
        """Load proficiency scores from database"""
        try:
            await db_manager.initialize()
            
            query = """
                SELECT skill, proficiency_score, total_attempts, successful_attempts
                FROM agent_proficiency
                WHERE agent_id = $1
            """
            
            async with db_manager.pool.acquire() as conn:
                rows = await conn.fetch(query, self.agent_id)
                
                for row in rows:
                    skill = row['skill']
                    self._proficiency_scores[skill] = row['proficiency_score']
                    self._attempt_counts[skill] = row['total_attempts']
                    self._success_counts[skill] = row['successful_attempts']
            
            logger.info(
                f"[CapabilityAssessor] Loaded {len(self._proficiency_scores)} "
                f"proficiency scores for {self.agent_id}"
            )
            
        except Exception as e:
            logger.error(f"[CapabilityAssessor] Failed to load from database: {e}")
    
    async def _save_to_db(self, skill: str, proficiency_score: float):
        """Save proficiency score to database"""
        try:
            await db_manager.initialize()
            
            query = """
                INSERT INTO agent_proficiency (
                    agent_id, skill, proficiency_score,
                    last_updated, total_attempts, successful_attempts
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (agent_id, skill)
                DO UPDATE SET
                    proficiency_score = $3,
                    last_updated = $4,
                    total_attempts = $5,
                    successful_attempts = $6
            """
            
            async with db_manager.pool.acquire() as conn:
                await conn.execute(
                    query,
                    self.agent_id,
                    skill,
                    proficiency_score,
                    datetime.utcnow(),
                    self._attempt_counts.get(skill, 0),
                    self._success_counts.get(skill, 0)
                )
            
        except Exception as e:
            logger.error(f"[CapabilityAssessor] Failed to save to database: {e}")
