# Dashboards

> The Vigilagent UI ships four operator dashboards. Three are existing
> (Integration Health, Learning Performance, Skill Library) and one is
> new with the Deep System Integration spec (Browser Health). All four
> read from the same `/api/integration/metrics` and `/api/runtime/health`
> endpoints documented in `API.md` §17a; alert thresholds are mirrored
> in `alerts.md`.

## 1. Integration Health

**Source.** `/api/integration/metrics` → the `integration` sub-object
(`backend/api/endpoints/dashboard.py:882`).

**Panels.**

- *Events processed* — line chart of `events_processed` and
  `events_failed` over the last hour.
- *Failure rate* — gauge of `failure_rate`, color band on
  thresholds below.
- *Circuit breaker trips* — single-stat of
  `circuit_breaker_trips`, with the per-trip log line surfaced
  inline.
- *Discovery batch backlog* — line chart of `pending_discoveries`
  and `last_batch_size` (handy for spotting when batching is doing
  its job).
- *Feature matrix* — table that pivots `features_enabled` against
  the rollout percentages from `config/integration.yaml`.

**Metrics read.**

`integration.events_processed`, `integration.events_failed`,
`integration.events_skipped`, `integration.failure_rate`,
`integration.circuit_breaker_trips`, `integration.pending_discoveries`,
`integration.batches_flushed`, `integration.last_batch_size`,
`integration.features_enabled`.

**Alert thresholds.**

| Metric                                          | Warning | Critical | Page on-call |
| ----------------------------------------------- | ------- | -------- | ------------ |
| `failure_rate` (sustained 5 min)                | `> 0.05`| `> 0.10` | yes (critical) |
| `circuit_breaker_trips` (any increase)          | `+1`    | —        | warning      |
| `pending_discoveries / event_batch_size`        | `> 0.8` | `= 1.0`  | warning      |

## 2. Learning Performance

**Source.** `/api/integration/metrics` → the `learning` sub-object
plus `performance.report` (the `performance_optimizer` summary already
surfaced by the dashboard endpoint).

**Panels.**

- *Patterns total* — single-stat of `learning.total_patterns`.
- *HTTP vs browser patterns* — stacked bar of `learning.http_patterns`
  vs `learning.browser_patterns`.
- *Pattern acquisition rate* — line chart, derived as
  `Δlearning.total_patterns / Δt` over the last hour.
- *Skill search latency p50/p99* — read from
  `performance.report.skill_search_latency_ms` (already exported by
  `performance_optimizer.get_performance_report()`).

**Metrics read.**

`learning.total_patterns`, `learning.http_patterns`,
`learning.browser_patterns`,
`performance.skill_search_latency_ms.p50`,
`performance.skill_search_latency_ms.p99`.

**Alert thresholds.**

| Metric                                       | Warning | Critical |
| -------------------------------------------- | ------- | -------- |
| Pattern acquisition rate (per hour, sustained 4h) | `< 1`   | `< 0.1`  |
| `skill_search_latency_ms.p99`                | `> 50`  | `> 200`  |

## 3. Skill Library

**Source.** `/api/integration/metrics` → the `skills` sub-object.

**Panels.**

- *Total skills* — single-stat of `skills.total_skills`.
- *Composition* — donut of `skills.http_skills`,
  `skills.browser_skills`, `skills.hybrid_skills`.
- *Acquisition rate* — line chart of `skills.acquisition_rate` over
  time. Rate is computed server-side as
  `total_skills / max(1, total_patterns)` so the chart shows how
  efficiently patterns turn into reusable skills.
- *Deprecated skills* — table of skills marked deprecated, joined
  client-side with the per-skill metadata returned by
  `/api/skills/{id}` (deprecation_reason, migration_path).
- *Migration status* — read from the most recent
  `POST /api/skills/migrate-v2` response, cached client-side.

**Metrics read.**

`skills.total_skills`, `skills.http_skills`, `skills.browser_skills`,
`skills.hybrid_skills`, `skills.acquisition_rate`,
plus `/api/skills/` and `/api/skills/{id}` for the deprecation table.

**Alert thresholds.**

| Metric                            | Warning | Critical |
| --------------------------------- | ------- | -------- |
| `skills.acquisition_rate`         | `< 0.3` | `< 0.1`  |
| Migration `failed` count          | `> 0`   | —        |

## 4. Browser Health (new)

**Source.** `/api/runtime/health` → the `browser_health` sub-object
(`backend/api/endpoints/runtime.py:97`,
`BrowserHealthMonitorExtension.get_browser_health_summary` /
`get_all_browser_health`).

**Panels.**

- *Engine status* — colored chips for OpenClaw and PinchTab from
  `browser.openclaw` and `browser.pinchtab`. Click reveals
  `browser.reasons` if the engine is `unavailable`.
- *Active contexts* — single-stat of
  `browser_health.summary.total_active_contexts`.
- *Browser memory* — line chart of
  `browser_health.summary.total_browser_memory_mb`. Threshold band
  drawn at 1 GB (the per-agent alert threshold inside
  `BrowserHealthMonitorExtension.report_browser_metrics`,
  `backend/core/agent_health_monitor.py:667`).
- *Per-agent table* — one row per
  `browser_health.agents[<agent>]`: `active_contexts`,
  `context_memory_mb`, `page_load_time_ms`, `screenshot_time_ms`,
  `browser_error_rate`, `browser_health_score`.
- *Health score histogram* — distribution of
  `browser_health_score` across agents. Pages on-call when any agent
  drops below 40 (matches the existing in-process critical alert
  emitted by the health monitor).

**Metrics read.**

`browser.openclaw`, `browser.pinchtab`, `browser.reasons`,
`browser_health.summary.total_active_contexts`,
`browser_health.summary.total_browser_memory_mb`,
`browser_health.summary.avg_browser_health_score`,
`browser_health.summary.browser_alerts`,
`browser_health.agents[*].context_memory_mb`,
`browser_health.agents[*].page_load_time_ms`,
`browser_health.agents[*].screenshot_time_ms`,
`browser_health.agents[*].browser_error_rate`,
`browser_health.agents[*].browser_health_score`.

**Alert thresholds.**

| Metric                                                | Warning      | Critical |
| ----------------------------------------------------- | ------------ | -------- |
| `browser_health.summary.avg_browser_health_score`     | `< 70`       | `< 40`   |
| `browser_health.summary.total_browser_memory_mb`      | `> 1024`     | `> 4096` |
| Per-agent `context_memory_mb` growth                  | `> 100 MB/h` | —        |
| Per-agent `browser_health_score`                      | `< 70`       | `< 40`   |
| `browser.openclaw` or `browser.pinchtab` `unavailable`| any          | both     |
