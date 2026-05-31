# Integration guide — adding a new coordinator consumer

> Audience: developers wiring a new cross-system signal through the
> `IntegrationCoordinator`. Five steps, one worked example. The
> coordinator's invariants (feature-flag gating, circuit breakers,
> bounded concurrency, no new event types) MUST hold for any new
> consumer; the steps below preserve them by construction.

## 1. Add the event type to the bus

Event vocabulary lives in `backend/core/hive.py:18-37`
(`EventType`). Add the new type there. Anything not in this enum is
treated as foreign by `EventBus._safe_execute` and routed to the dead
letter queue.

```python
# backend/core/hive.py
class EventType(str, Enum):
    ...
    EVIDENCE_COLLECTED = "EVIDENCE_COLLECTED"
```

Producers publish via `bus.publish("EVIDENCE_COLLECTED", payload,
scan_id=scan_id)`. Per-scan events route through
`ScanContext.event_queue`; global events fan out immediately. Both
flows are unchanged — the coordinator subscribes the same way as any
other handler.

## 2. Subscribe in the coordinator

`IntegrationCoordinator.initialize()` at
`backend/core/integration_coordinator.py:177` is the only place that
calls `bus.subscribe(...)`. Add your handler there.

The handler MUST:

- Accept either a dict or an event-like object (use `_event_data` and
  `_event_scan_id` shims at the top of the module).
- Short-circuit when the feature flag is off:
  `if not self.config.enable_<your_feature>: return`.
- Short-circuit when the rollout percentage excludes this scan:
  `if not self.config.should_enable_for_scan(scan_id, "<feature>"):
  self._metrics.events_skipped += 1; return`.
- Run the actual downstream call inside `self._cb_<your_dep>.call(...)`
  (declare the breaker in `__init__` next to the existing two).
- Bump `_metrics.events_processed` on success and
  `_metrics.events_failed` on exception.
- Stay under the learning semaphore if the work is learning-shaped:
  `async with self._learning_semaphore:`.

The coordinator publishes nothing of its own. If your consumer needs
to fan out a downstream signal, raise the appropriate existing
event — never invent a new one inside the coordinator.

## 3. Add a feature flag in `IntegrationConfig`

Two fields go into `backend/core/integration_config.py` per feature:
the boolean `enable_<feature>` and the integer
`<feature>_rollout_pct`. Wire them into `from_env()` (env-var names
follow the `ENABLE_<FEATURE>` / `<FEATURE>_ROLLOUT_PCT` convention),
into `get_feature_status()` for the dashboard, and into
`validate()` for the percentage-range check.

Mirror the same fields in `config/integration.yaml` under the
`integration:` block, annotated with the owning task id, with both
fields starting at the safe-default values
(`enable_<feature>: false`, `<feature>_rollout_pct: 0`).

Confirm the rollout gate by calling
`should_enable_for_scan(scan_id, "<feature>")` from a test — it uses
consistent hashing over `scan_id` so the same scan always gets the
same answer.

## 4. Write a smoke test

Land the test next to the existing integration suite at
`tests/integration/test_deep_system_integration.py`. The shape that
matches the existing suite:

- Build the coordinator with mocked dependencies (`MockEventBus`,
  `MockLearningEngine`, etc. — the `.kiro/specs/deep-system-integration/design.md`
  §"Test Infrastructure" section has the patterns).
- Call `await coordinator.initialize()`, publish your event, sleep
  briefly to let the handler run, then assert on
  `coordinator.get_integration_metrics()`.
- Cover the four behaviour modes: flag off, flag on / rollout 0,
  flag on / rollout 100, flag on / dependency raises. The last one
  must not propagate — it must increment `events_failed` and
  eventually trip the breaker.

## 5. Document the endpoint in `API.md`

If your consumer exposes any HTTP surface (most do, even if only a new
field on `/api/integration/metrics`), add it to `API.md` §17a. Match
the format used by the three existing endpoints there: HTTP verb,
path, query params, request/response example, error codes, auth
requirement.

If your consumer adds a metric field to the existing payload (e.g. an
extra counter under `integration.*`), append it to the table in
`runbooks/integration_ops.md` §1 and decide whether it deserves an
alert in `alerts.md`. A new metric without an alert and without a
dashboard panel is invisible.

---

## Worked example — `EVIDENCE_COLLECTED` consumer

```python
# 1. backend/core/hive.py — add to EventType enum
class EventType(str, Enum):
    ...
    EVIDENCE_COLLECTED = "EVIDENCE_COLLECTED"

# 2. backend/core/integration_coordinator.py
class IntegrationCoordinator:
    def __init__(self, *, bus, learning_engine, ..., forensic_collector, config=None):
        ...
        self.forensic_collector = forensic_collector
        self._cb_evidence = _LocalCircuitBreaker(
            name="evidence_quality_learning",
            failure_threshold=self.config.circuit_breaker_threshold,
            recovery_timeout=float(self.config.circuit_breaker_timeout_s),
        )

    async def initialize(self) -> None:
        ...
        await self.bus.subscribe("EVIDENCE_COLLECTED", self._on_evidence)

    async def _on_evidence(self, event):
        if not self.config.enable_forensic_learning:
            return
        scan_id = _event_scan_id(event)
        if not self.config.should_enable_for_scan(scan_id, "forensic_learning"):
            self._metrics.events_skipped += 1
            return
        data = _event_data(event)
        try:
            async with self._learning_semaphore:
                await self._cb_evidence.call(
                    lambda: self.forensic_collector.learn_evidence_requirements(data, scan_id)
                )
            self._metrics.events_processed += 1
        except _LocalCircuitBreaker.CircuitOpen:
            self._metrics.events_skipped += 1
        except Exception:
            self._metrics.events_failed += 1
            logger.exception("evidence learning failed for %s", scan_id)
```

Step 3 reuses the existing `enable_forensic_learning` flag (it was
added with the spec — see `IntegrationConfig`). Step 4 lands a smoke
test asserting that an `EVIDENCE_COLLECTED` event with the flag off is
a no-op, and with the flag on at 100 % rollout calls
`forensic_collector.learn_evidence_requirements` exactly once. Step 5
adds nothing new to `API.md` — the metrics already surface through
`integration.events_processed`.
