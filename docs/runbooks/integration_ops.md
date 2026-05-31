# Runbook — Deep System Integration ops

> Companion to `docs/ARCHITECTURE.md` Appendix A. Targets the on-call
> operator who has to tell — at a glance — whether the
> `IntegrationCoordinator` is healthy, and recover it when it isn't.
> Code paths cited inline so you can read source alongside the steps.

## 1. Daily health check

Single curl against the local backend (default `127.0.0.1:8000`):

```bash
curl -s http://127.0.0.1:8000/api/integration/metrics | jq .integration
```

Expected fields and interpretation:

| Field                    | Healthy range            | What it means                                                                                  |
| ------------------------ | ------------------------ | ---------------------------------------------------------------------------------------------- |
| `events_processed`       | strictly increasing      | Count of cross-system events the coordinator has handled since boot.                           |
| `events_failed`          | `< 1 %` of processed     | Failures inside a downstream call (learning, healing, routing). See `failure_rate`.            |
| `events_skipped`         | low                      | Events dropped by the rollout-percentage gate. Spikes during cohort bumps are normal.          |
| `failure_rate`           | `< 0.10`                 | Convenience field = `events_failed / max(events_processed, 1)`.                                |
| `circuit_breaker_trips`  | `0` (cumulative)         | Any non-zero is a real signal — the coordinator has tripped at least once and degraded.       |
| `pending_discoveries`    | `< event_batch_size`     | Depth of the unflushed `BROWSER_DISCOVERY` batch. A sustained ceiling means the drain stalled. |
| `batches_flushed`        | strictly increasing      | Counts every flushed discovery batch.                                                          |
| `last_batch_size`        | `≤ event_batch_size`     | Sanity check — should never exceed the configured batch size.                                  |
| `features_enabled`       | matches `integration.yaml` | Sanity check that the running config matches what's on disk.                                  |

The full payload also includes `learning`, `skills`, `health`, and
`performance` sub-blocks; see `API.md` §17a for shapes.

## 2. Common incidents

### 2.1 Circuit breaker tripped

**Symptom.** `/api/integration/metrics` shows
`integration.circuit_breaker_trips > 0` and `events_skipped` climbing
faster than `events_processed`. Logs contain
`Circuit '<name>' tripped open after 5 consecutive failures`.

**Recovery.**

1. Identify the breaker — log line names it
   (`browser_vulnerability_learning` or `discovery_learning`).
2. Pull the underlying cause from logs filtered by the same scan_id.
   Vulnerability-learning trips usually point at Redis or the skill
   library; discovery-learning trips usually point at the learning
   engine's pattern store.
3. Once the dependency is back, **wait** — the breaker half-opens
   automatically after `circuit_breaker_timeout_s` (default 60 s,
   `IntegrationConfig.circuit_breaker_timeout_s`). The next successful
   event closes it.
4. If you cannot wait (e.g. you fixed the dependency and need traffic
   through immediately), restart the backend. Breakers reset on init.
5. If trips repeat within the same hour, raise rollout to 0 for the
   affected feature in `config/integration.yaml` and restart. See
   §2.4 (Rollback).

**Do not** disable the circuit breaker entirely
(`CIRCUIT_BREAKER_ENABLED=false`). It is the only thing keeping a
downstream outage from cascading into the publish loop.

### 2.2 Event queue backlog

**Symptom.** `pending_discoveries` sits at the `event_batch_size`
ceiling for more than a minute, and `batches_flushed` does not advance.

**Recovery.**

1. Confirm the drain task is alive. Look for the asyncio task name
   `ic_batch_drain` in the backend logs at startup. If you see
   `IntegrationCoordinator shutdown` without a corresponding init,
   restart the backend.
2. Inspect `events_skipped` — if it is climbing, the batch is being
   short-circuited by a feature flag (rollout percentage). This is
   expected during a cohort bump but should not produce a backlog. If
   it does, lower the rollout for that feature.
3. If the backlog persists after a restart, drop `event_batch_size`
   in `config/integration.yaml` (e.g. 50 → 20) and restart. Smaller
   batches flush faster but burn more CPU on the learning side.

### 2.3 Redis disconnect

**Symptom.** Backend logs include
`DistributedEventBus.start ... silently dropping to local-only`
(`backend/core/hive.py:283-291`) and the coordinator's vuln-learning
breaker starts tripping because the idempotency lock cannot be
acquired.

**Recovery.**

1. Verify Redis: `redis-cli -h 127.0.0.1 -p 6379 PING` should return
   `PONG`.
2. If Redis is up but the backend can't reach it, check `REDIS_URL` in
   the active environment and the backend's network egress.
3. Once Redis is back, the bus reattaches lazily; coordinator breakers
   recover on the next half-open window. No restart required unless
   trips persist past two breaker timeouts (~120 s by default).
4. If Redis will be down for more than a few minutes, set the rollout
   for `browser_learning` to `0` in `config/integration.yaml` and
   restart. The coordinator falls back to the in-process `EventBus` and
   skips browser-vuln learning until you bump the percentage back.

## 3. Skill library maintenance

The v2 skill schema (semver, capabilities, execution context, deprecation
metadata) is a one-shot migration. Run it after a fresh deploy that
includes the `skill_library_v2` feature, and again any time
`backend/skills/migrations/v2_browser.py` is modified.

```bash
# Dry-run: report what would change without writing.
python -m backend.skills.migrations.v2_browser --dry-run

# Apply: writes the new shape, idempotent on already-migrated rows.
python -m backend.skills.migrations.v2_browser --apply
```

The same migration is exposed over HTTP as
`POST /api/skills/migrate-v2` (auth required — see `API.md` §17a). Use
the CLI on the host, the HTTP endpoint when you're remote.

Validation after migration:

```bash
curl -s http://127.0.0.1:8000/api/integration/metrics | jq '.skills'
# total_skills should match what the migration reported as scanned.
# http_skills + browser_skills + hybrid_skills should equal total_skills.
```

If `failed > 0` in the migration report, the response body lists the
offending skill ids. Re-running with `--apply` is safe: the migration
is idempotent.

## 4. Rollback procedure

The rollout-percentage field is the kill switch — flipping flags off is
**not** required.

1. Edit `config/integration.yaml`. Set the offending feature's
   `*_rollout_pct` to `0`. Leave `enable_*` as-is so the audit trail
   shows the feature was rolled back, not turned off.
2. Restart the backend (`uvicorn`, `docker compose restart backend`,
   or your process manager's equivalent).
3. Confirm: `/api/integration/metrics` should report
   `events_skipped` climbing on the next scan and the affected handler
   should no-op (no downstream call, no trip).
4. File an incident note — restart-only rollbacks must be auditable so
   the next on-call can correlate the cohort bump with the symptom.

For a **full** rollback (all features off), set every `*_rollout_pct`
to `0`. The coordinator continues to subscribe and count events, so
metrics keep flowing even with every handler short-circuited; this is
the safe steady state.
