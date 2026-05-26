"""
DECISION LOGGER
Records decision rationale and confidence levels.

This logger:
1. Logs decisions with rationale and confidence
2. Records rejected alternatives
3. Provides decision query capabilities
4. Formats decisions for reports
5. Maintains audit trails
"""

import logging
import uuid
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from backend.core.self_awareness_config import SelfAwarenessConfig
from backend.core.database import db_manager
from backend.core.tracing import get_tracer, trace_span

logger = logging.getLogger("DecisionLogger")
tracer = get_tracer()


@dataclass
class Decision:
    """Represents a logged decision"""
    decision_id: str
    agent_id: str
    timestamp: datetime
    action_type: str
    rationale: str
    confidence: float
    alternatives_considered: list
    context: Dict[str, Any]
    finding_id: Optional[str] = None


class DecisionLogger:
    """Logs agent decisions with rationale"""
    
    def __init__(self, agent_id: str, config: SelfAwarenessConfig):
        self.agent_id = agent_id
        self.config = config
        self._pending_decisions = []
        
        logger.info(f"[DecisionLogger] Initialized for agent {agent_id}")
    
    async def log_decision(
        self,
        action: Any,
        rationale: str,
        confidence: float,
        context: Dict[str, Any],
        alternatives: Optional[List[Any]] = None
    ) -> str:
        """Log a decision"""
        decision_id = str(uuid.uuid4())
        
        # Validate confidence
        confidence = max(0.0, min(1.0, confidence))
        
        decision = Decision(
            decision_id=decision_id,
            agent_id=self.agent_id,
            timestamp=datetime.utcnow(),
            action_type=action.action_type.value if hasattr(action, 'action_type') else str(action),
            rationale=rationale[:1000],  # Truncate long rationales
            confidence=confidence,
            alternatives_considered=alternatives or [],
            context=context
        )
        
        self._pending_decisions.append(decision)
        
        # Persist to database
        await self._save_to_db(decision)
        
        logger.debug(f"[DecisionLogger] Logged decision {decision_id}")
        
        return decision_id
    
    async def _save_to_db(self, decision: Decision):
        """Save decision to database"""
        try:
            await db_manager.initialize()
            
            query = """
                INSERT INTO agent_decisions (
                    decision_id, agent_id, timestamp, action_type,
                    rationale, confidence, alternatives_considered, context
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """
            
            async with db_manager.pool.acquire() as conn:
                await conn.execute(
                    query,
                    decision.decision_id,
                    decision.agent_id,
                    decision.timestamp,
                    decision.action_type,
                    decision.rationale,
                    decision.confidence,
                    decision.alternatives_considered,
                    decision.context
                )
        except Exception as e:
            logger.error(f"[DecisionLogger] Failed to save decision: {e}")
    
    async def flush(self):
        """Flush pending decisions"""
        self._pending_decisions.clear()
    
    async def query_decisions(
        self,
        agent_id: Optional[str] = None,
        action_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        min_confidence: Optional[float] = None,
        limit: int = 100
    ) -> List[Decision]:
        """Query decisions with filters
        
        Args:
            agent_id: Filter by agent ID
            action_type: Filter by action type
            start_time: Filter by start time
            end_time: Filter by end time
            min_confidence: Filter by minimum confidence
            limit: Maximum number of results
            
        Returns:
            List of matching decisions
        """
        try:
            await db_manager.initialize()
            
            # Build query
            conditions = []
            params = []
            param_count = 1
            
            if agent_id:
                conditions.append(f"agent_id = ${param_count}")
                params.append(agent_id)
                param_count += 1
            
            if action_type:
                conditions.append(f"action_type = ${param_count}")
                params.append(action_type)
                param_count += 1
            
            if start_time:
                conditions.append(f"timestamp >= ${param_count}")
                params.append(start_time)
                param_count += 1
            
            if end_time:
                conditions.append(f"timestamp <= ${param_count}")
                params.append(end_time)
                param_count += 1
            
            if min_confidence is not None:
                conditions.append(f"confidence >= ${param_count}")
                params.append(min_confidence)
                param_count += 1
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            query = f"""
                SELECT decision_id, agent_id, timestamp, action_type,
                       rationale, confidence, alternatives_considered, context, finding_id
                FROM agent_decisions
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT ${param_count}
            """
            params.append(limit)
            
            async with db_manager.pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
                
                decisions = []
                for row in rows:
                    decisions.append(Decision(
                        decision_id=row['decision_id'],
                        agent_id=row['agent_id'],
                        timestamp=row['timestamp'],
                        action_type=row['action_type'],
                        rationale=row['rationale'],
                        confidence=row['confidence'],
                        alternatives_considered=row['alternatives_considered'] or [],
                        context=row['context'] or {},
                        finding_id=row.get('finding_id')
                    ))
                
                return decisions
                
        except Exception as e:
            logger.error(f"[DecisionLogger] Query failed: {e}")
            return []
    
    async def get_decision_chain(self, finding_id: str) -> List[Decision]:
        """Get complete decision chain for a finding
        
        Args:
            finding_id: The finding ID to get decisions for
            
        Returns:
            List of decisions related to the finding
        """
        try:
            await db_manager.initialize()
            
            query = """
                SELECT decision_id, agent_id, timestamp, action_type,
                       rationale, confidence, alternatives_considered, context, finding_id
                FROM agent_decisions
                WHERE finding_id = $1
                ORDER BY timestamp ASC
            """
            
            async with db_manager.pool.acquire() as conn:
                rows = await conn.fetch(query, finding_id)
                
                decisions = []
                for row in rows:
                    decisions.append(Decision(
                        decision_id=row['decision_id'],
                        agent_id=row['agent_id'],
                        timestamp=row['timestamp'],
                        action_type=row['action_type'],
                        rationale=row['rationale'],
                        confidence=row['confidence'],
                        alternatives_considered=row['alternatives_considered'] or [],
                        context=row['context'] or {},
                        finding_id=row.get('finding_id')
                    ))
                
                return decisions
                
        except Exception as e:
            logger.error(f"[DecisionLogger] Failed to get decision chain: {e}")
            return []
    
    def format_for_report(self, decision: Decision) -> str:
        """Format decision rationale for human-readable report
        
        Args:
            decision: The decision to format
            
        Returns:
            Human-readable formatted decision
        """
        lines = [
            f"Decision: {decision.action_type}",
            f"Agent: {decision.agent_id}",
            f"Timestamp: {decision.timestamp.isoformat()}",
            f"Confidence: {decision.confidence:.2f}",
            f"",
            f"Rationale:",
            f"{decision.rationale}",
        ]
        
        if decision.alternatives_considered:
            lines.append("")
            lines.append("Alternatives Considered:")
            for alt in decision.alternatives_considered:
                lines.append(f"  - {alt}")
        
        return "\n".join(lines)
