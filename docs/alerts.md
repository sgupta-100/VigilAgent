# Alert rules — Deep System Integration

> Plain-text rule list, deliberately not a monitoring-tool DSL. Translate
> these into your alerting backend (Prometheus / OpenSearch / Datadog /
> CloudWatch — whatever you run). Every rule cites the metric source so
> the translation is mechanical.

## Conventions

- All metrics come from `GET /api/integration/metrics` and
  `GET /api/runtime/health` (see `API.md` §17a).
- "5 min sustained" means the rule must hold for five consecutive
  one-minute windows before the alert fires. This eats brief spikes
  during cohort bumps and dependency restarts.
- Severities:
  - **page** — wakes the on-call rotation. Reserved for production
    impact.
  - **warning** — chat / email. The next business day is fine unless it
    escalates.
- Cumulative counters (`circuit_breaker_trips`, `events_failed`) reset
  on backend restart. Compare against the per-window delta, not the
  raw value, in your alerting backend.

## Rules

### 1. High failure rate — page

- **Source.** `integration.events_failed`, `integration.events_processed`
  from `/api/integration/metrics`.
- **Condition.**
  `events_failed / max(events_processed, 1) > 0.10`
  sustained for 5 min.
- **Severity.** page on-call.
- **Why.** A 10 % failure rate over five minutes means the coordinator
  is steadily dropping cross-system signals. Past the circuit-breaker
  threshold this becomes self-correcting; below it, signals are lost
  silently.
- **Runbook.** `runbooks/integration_ops.md` §2.1 (circuit breaker
  tripped) — same root causes apply even when the breaker has not yet
  fired.

### 2. Circuit breaker tripped — warning

- **Source.** `integration.circuit_breaker_trips` from
  `/api/integration/metrics`.
- **Condition.** Any positive delta. Cumulative counter; alert on
  *change*, not absolute value.
- **Severity.** warning.
- **Why.** A trip means the coordinator opened a breaker for at least
  60 s (the default `circuit_breaker_timeout_s`), so cross-system
  learning was paused. Investigate the dependency named in the log
  line (`browser_vulnerability_learning` or `discovery_learning`).
- **Runbook.** `runbooks/integration_ops.md` §2.1.

### 3. Slow skill search — warning

- **Source.** `performance.skill_search_latency_ms.p99` from
  `/api/integration/metrics` (`performance_optimizer.get_performance_report()`).
- **Condition.** `p99 > 50 ms` sustained for 10 min.
- **Severity.** warning.
- **Why.** The skill library promised O(1) lookups via the capability /
  context / framework indexes. A p99 above 50 ms means an index has
  been bypassed or the library has grown past the cache budget.
- **Runbook.** Run `/api/skills/reload`. If the latency does not return
  to baseline within five minutes, drop the rollout for
  `skill_library_v2` to 0 in `config/integration.yaml` and restart.

### 4. Browser memory leak — warning

- **Source.** `browser_health.agents[<agent>].context_memory_mb`
  from `/api/runtime/health`.
- **Condition.** Per-agent `context_memory_mb` increases by more than
  100 MB over any rolling 60 min window without a corresponding
  increase in `active_contexts`.
- **Severity.** warning.
- **Why.** Steady memory growth without context growth is the
  signature of leaked browser contexts that
  `BrowserHealthMonitorExtension` couldn't reclaim. The healing engine
  will eventually close idle contexts (`heal_browser_memory`), but a
  sustained leak indicates the trigger isn't firing.
- **Runbook.** Confirm with the per-agent table on the Browser Health
  dashboard. If a single agent is the leaker, restart that agent's
  worker; if it's spread across agents, restart the backend. File a
  ticket if the pattern repeats within the same week — that's an
  upstream bug in `recovery_engine.heal_browser_memory`.

## Companion rules (optional)

These are not required by the spec but follow naturally from the
existing health-monitor outputs and pair well with the four above.

### 5. Browser engine offline — warning / page

- **Source.** `browser.openclaw`, `browser.pinchtab` from
  `/api/runtime/health`.
- **Condition.**
  - One engine `unavailable` → warning.
  - Both engines `unavailable` → page (browser stack is gone, recon
    falls back to HTTP probes only).

### 6. Browser health score critical — page

- **Source.** `browser_health.agents[<agent>].browser_health_score`.
- **Condition.** Any agent's score drops below 40.
- **Severity.** page.
- **Why.** Mirrors the in-process critical alert at
  `backend/core/agent_health_monitor.py:651`. The coordinator's
  recovery path takes time — paging keeps a human in the loop while
  the healing engine does its work.

### 7. Discovery batch saturated — warning

- **Source.** `integration.pending_discoveries`,
  `integration.last_batch_size` (compared to
  `IntegrationConfig.event_batch_size`).
- **Condition.** `pending_discoveries == event_batch_size` and
  `batches_flushed` does not advance for 60 s.
- **Severity.** warning.
- **Why.** The drain task has stalled. See
  `runbooks/integration_ops.md` §2.2.
