# Pre-deploy checklist

> Run through this before every Deep System Integration deploy
> (canary or full). Every item is binary — green or stop. The end state
> is "feature flags enabled, percentages at the cohort target, canary
> watched for 24 h before bumping". See `runbooks/integration_ops.md`
> for what to do if any item fails after deploy.

## 0. Prerequisites

- [ ] You have read `runbooks/integration_ops.md` end-to-end.
- [ ] You have shell access to the host and `curl` against
      `127.0.0.1:8000`.
- [ ] You can edit `config/integration.yaml` and restart the backend.

## 1. Docker Desktop running

The recon stack runs in Docker (`docker/recon/Dockerfile`); the
TerminalEngine prefers the Docker backend when it is available
(`backend/core/terminal_engine.py`).

- [ ] `docker info` succeeds.
- [ ] `docker ps --format "{{.Names}}"` includes a running recon
      container (the platform auto-detects via
      `running_recon_container()` in
      `backend/tools/recon/docker_runtime.py:167`; common
      auto-detected name is `reverent_banach`).

If Docker is not running, the platform still boots — recon falls back
to local PATH binaries — but performance and tool coverage degrade.

## 2. Redis on 6379 (PING true)

Redis backs the distributed event bus, idempotency locks for
browser-vuln learning, and the migration lock for
`POST /api/skills/migrate-v2`.

- [ ] `redis-cli -h 127.0.0.1 -p 6379 PING` returns `PONG`.
- [ ] Backend logs at startup do **not** include
      `DistributedEventBus.start ... silently dropping to local-only`
      (`backend/core/hive.py:283-291`).

If Redis is unreachable, the backend continues with the in-process
EventBus. Browser-vuln learning will trip its circuit breaker on first
call. Don't deploy with Redis missing.

## 3. `python -m compileall -q backend` clean

A syntax error here will not be caught by FastAPI's lazy imports until
the offending router is hit, and then in production. Run it cold.

- [ ] `python -m compileall -q backend` exits 0 with no output.
- [ ] Same for `backend/skills/` if you've touched migrations:
      `python -m compileall -q backend/skills`.

## 4. Feature flags off in prod for rollout

The cohort percentages in `config/integration.yaml` are the kill
switch. Production deploys start from the same baseline every time.

- [ ] `config/integration.yaml` for the prod environment has every
      `*_rollout_pct: 0` before deploy.
- [ ] Environment variables (`ENABLE_BROWSER_LEARNING`,
      `BROWSER_LEARNING_ROLLOUT_PCT`, etc.) **either** match the YAML
      **or** are unset. Mixed states are a footgun — env wins, and
      operators read the YAML.

After the canary window (step 7), you bump the percentages following
the schedule in `ARCHITECTURE.md` Appendix A.4.

## 5. Load `config/integration.yaml` validated

The dataclass has a `validate()` method that runs at first read
(`IntegrationConfig.validate` in
`backend/core/integration_config.py`). It catches percentage
out-of-range, non-positive concurrency, and bad sample rates.

- [ ] Run `python -c "from backend.core.integration_config import
      get_integration_config; get_integration_config()"` against the
      target environment. Exit 0 means the YAML + env combo is valid.
- [ ] Backend logs at startup contain
      `Integration configuration loaded` with the four feature flags
      and rollout percentages echoed back.

## 6. Run `pytest tests/integration/test_deep_system_integration.py` — all green

The integration suite lives at
`tests/integration/test_deep_system_integration.py` (defined by the
spec in `.kiro/specs/deep-system-integration/tasks.md` §15). It
exercises the coordinator end-to-end with mocked downstreams.

- [ ] `pytest tests/integration/test_deep_system_integration.py -q`
      exits 0.
- [ ] No tests are skipped without an explicit reason in the test
      output — skipped property tests usually mean Hypothesis
      couldn't satisfy a precondition, which is its own warning sign.

If your repo also runs the broader integration suite
(`tests/integration/`), run that too — `test_engine_coordination.py`
and `test_agent_workflows.py` cover adjacent paths and will catch a
regression that the deep-integration suite alone misses.

## 7. Monitor first 1 % canary for 24 h before bumping

The cohort schedule in `ARCHITECTURE.md` Appendix A.4 starts at 10 %.
For a fresh deploy of a new feature, run a 1 % canary first (set the
percentage to `1` for one feature only) and watch.

- [ ] At T+1h: `failure_rate < 0.05`, `circuit_breaker_trips == 0`.
- [ ] At T+4h: same, plus `pending_discoveries < event_batch_size` at
      every read.
- [ ] At T+24h: same, plus the four warning-tier rules in
      `alerts.md` (slow skill search, browser memory leak, discovery
      batch saturated, browser engine offline) have produced zero
      alerts.

Only after the 24 h canary is clean do you bump to the cohort target
(10 % for browser learning, 25 % for skill library v2, etc.).

## Final sanity

```bash
curl -s http://127.0.0.1:8000/api/integration/metrics \
  | jq '{integration: .integration, skills: .skills.total_skills, learning: .learning.total_patterns}'
```

A healthy deployment shows `events_processed > 0` within five minutes
of first scan, `circuit_breaker_trips == 0`, and the skill / learning
counts you expected from the migration report.
