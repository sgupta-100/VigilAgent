import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Set

class ScanContext:
    def __init__(self, scan_id: str = None):
        self.scan_id = scan_id or str(uuid.uuid4())
        
        # 1. State Isolation Barriers (Fixes Invariant 8: Cross-Scan Bleed)
        self.baseline_cache: Dict[str, Any] = {}
        self.diff_cache: Dict[str, Any] = {}
        
        # 1.5 Chronological Transcript (Replaces global workflow_state Blackboard)
        self.transcript: list[str] = []
        self.workflow_state: Dict[str, Any] = {} # Deprecated: kept only for backwards compatibility
        
        # 2. Causal Ordering (Fixes Invariant 21)
        self.event_queue = asyncio.Queue()
        
        # 3. Deduplication Window (Fixes Invariant 7)
        self._recent_events: Set[str] = set()
        
        # 4. Cancellation Propagation (Fixes Invariant 24)
        self.is_cancelled: bool = False

    def append_event(self, event: Any, *, max_payload_chars: int = 4000) -> str:
        """Append a canonical chronological [Event] block to the scan transcript."""
        payload = getattr(event, "payload", {})
        try:
            payload_text = json.dumps(payload, sort_keys=True, default=str)
        except Exception:
            payload_text = str(payload)
        if len(payload_text) > max_payload_chars:
            payload_text = payload_text[:max_payload_chars] + "...[truncated]"

        timestamp = getattr(event, "timestamp", None)
        if isinstance(timestamp, datetime):
            timestamp_text = timestamp.isoformat()
        else:
            timestamp_text = str(timestamp or datetime.utcnow().isoformat())

        event_type = getattr(getattr(event, "type", ""), "value", getattr(event, "type", "UNKNOWN"))
        block = (
            "[Event]\n"
            f"id: {getattr(event, 'id', '')}\n"
            f"scan_id: {getattr(event, 'scan_id', self.scan_id)}\n"
            f"timestamp: {timestamp_text}\n"
            f"type: {event_type}\n"
            f"source: {getattr(event, 'source', 'unknown')}\n"
            f"payload: {payload_text}\n"
            "[/Event]"
        )
        self.transcript.append(block)
        return block

    def transcript_text(self, *, tail: int | None = None) -> str:
        events = self.transcript[-tail:] if tail else self.transcript
        return "\n\n".join(events)
