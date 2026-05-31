# Deployment topology

> Topology + environment matrix for the Vigilagent backend with the
> Deep System Integration coordinator turned on. The end-to-end
> install / Nginx / systemd guide lives in `DEPLOYMENT.md`; this doc
> is the operator's one-pager for *what runs where* and *how to talk
> to it*.

## 1. Component map

```text
        ┌─────────────────────┐
        │  Operator browser   │
        │  React UI (Vite)    │
        └──────────┬──────────┘
                   │ HTTP + WS
                   ▼
        ┌─────────────────────┐         ┌──────────────────────┐
        │  Backend (FastAPI)  │ ◀─────▶ │  Redis (6379)        │
        │  uvicorn :8000      │         │  bus + locks + cache │
        │  IntegrationCoord.  │         └──────────────────────┘
        └──────────┬──────────┘
                   │
        ┌──────────┴───────────┬────────────────────┐
        ▼                      ▼                    ▼
 ┌──────────────┐     ┌──────────────────┐  ┌──────────────────┐
 │ Recon        │     │ PinchTab         │  │ OpenClaw         │
 │ container    │     │ control plane    │  │ Playwright/      │
 │ (Docker)     │     │ :9867            │  │ Chromium engine  │
 │ name:        │     │ fast DOM/scrape  │  │ deep automation  │
 │ reverent_    │     │                  │  │                  │
 │ banach       │     └──────────────────┘  └──────────────────┘
 │ (auto-       │
 │  detected)   │
 └──────┬───────┘
        │ docker exec
        ▼
   39 recon tools
   on PATH inside
   the container
```

Notes:

- The backend is a single Python process by default. `uvicorn :8000`
  hosts both REST and WebSocket
  (`backend/main.py:332`, modes
  `serve|master|worker|cluster`).
- Redis is **optional but strongly recommended**. Without it, the bus
  drops to in-process and browser-vuln learning loses its
  idempotency lock; the coordinator still runs, just degraded.
- The recon container is auto-detected by name when running
  (`running_recon_container()` in
  `backend/tools/recon/docker_runtime.py:167`). `reverent_banach` is
  a common operator-named container; any running container started
  from the recon image works.
- PinchTab and OpenClaw are independent. The
  `BrowserOrchestrator` selects between them at call time
  (`BrowserEngine.AUTO`, `OPENCLAW`, `PINCHTAB`). Either or both can
  be offline; the orchestrator falls back through the candidate
  list and finally raises `BrowserUnavailable`.

## 2. Environment variable matrix

| Variable                              | Default                          | Used by                               | Notes |
| ------------------------------------- | -------------------------------- | ------------------------------------- | ----- |
| `REDIS_URL`                           | (unset)                          | `EventBus`, idempotency locks         | Setting it switches the bus to `DistributedEventBus`. |
| `STRATEGIC_MODEL`                     | `openai/gpt-oss-20b`             | Cortex strategic LLM                  | One of the §11-allowed models. |
| `TACTICAL_MODEL`                      | `gemini-2.5-flash`               | Cortex tactical LLM                   | One of the §11-allowed models. |
| `RECON_MAX_WAIT_SECONDS`              | `180`                            | Orchestrator phase gate               | Hard cap on recon completion. |
| `VIGILAGENT_RECON_CONTAINER`          | (auto-detect)                    | TerminalEngine Docker backend         | Override when multiple containers exist. |
| `VIGILAGENT_RECON_IMAGE`              | `vigilagent/recon:latest`        | docker_runtime                        | Image to look for. |
| `RECON_DOCKER_NETWORK`                | `bridge`                         | docker_runtime                        | Container network. |
| `TERMINAL_PREFER_DOCKER`              | `true`                           | TerminalEngine                        | Prefer Docker over local PATH. |
| `PINCHTAB_BASE_URL`                   | `http://127.0.0.1:9867`          | PinchTab client                       | Override for non-default control-plane host. |
| `ENABLE_BROWSER_LEARNING`             | `false`                          | `IntegrationConfig`                   | Master flag for browser learning. |
| `BROWSER_LEARNING_ROLLOUT_PCT`        | `0`                              | `IntegrationConfig`                   | 0–100 cohort percentage. |
| `ENABLE_CROSS_HEALING`                | `false`                          | `IntegrationConfig`                   | Master flag for cross-system healing. |
| `CROSS_HEALING_ROLLOUT_PCT`           | `0`                              | `IntegrationConfig`                   | Cohort percentage. |
| `ENABLE_FORENSIC_LEARNING`            | `false`                          | `IntegrationConfig`                   | Master flag for forensic learning. |
| `FORENSIC_LEARNING_ROLLOUT_PCT`       | `0`                              | `IntegrationConfig`                   | Cohort percentage. |
| `ENABLE_INTELLIGENT_ROUTING`          | `false`                          | `IntegrationConfig`                   | Master flag for routing. |
| `INTELLIGENT_ROUTING_ROLLOUT_PCT`     | `0`                              | `IntegrationConfig`                   | Cohort percentage. |
| `EVENT_BATCH_SIZE`                    | `10`                             | `IntegrationCoordinator`              | Tune for `BROWSER_DISCOVERY` storms. |
| `EVENT_BATCH_TIMEOUT_MS`              | `1000`                           | `IntegrationCoordinator`              | Drain interval. |
| `MAX_CONCURRENT_LEARNING`             | `5`                              | `IntegrationCoordinator`              | Semaphore cap on learning fan-out. |
| `CIRCUIT_BREAKER_ENABLED`             | `true`                           | `_LocalCircuitBreaker`                | Do not disable in prod. |
| `CIRCUIT_BREAKER_THRESHOLD`           | `5`                              | `_LocalCircuitBreaker`                | Consecutive failures to trip. |
| `CIRCUIT_BREAKER_TIMEOUT_S`           | `60`                             | `_LocalCircuitBreaker`                | Recovery window. |
| `LOCK_TTL_SECONDS`                    | `300`                            | Distributed locks                     | Idempotency + migration. |
| `TRACING_ENABLED`                     | `true`                           | OpenTelemetry hooks                   | Disable in air-gapped deploys. |
| `TRACING_SAMPLE_RATE`                 | `1.0`                            | OpenTelemetry hooks                   | Lower under load. |

`.env.example` in the repo root is the canonical list; this table is
the operator's view, scoped to topology + integration. Anything in
`config/integration.yaml` is overridable by the variable above with
the same name.

## 3. Persistent volumes

| Path                                            | Owner                     | Purpose                                                        | Backup? |
| ----------------------------------------------- | ------------------------- | -------------------------------------------------------------- | ------- |
| `scan_states/` (or wherever `scan_state.db` lives) | `ScanStateDB`           | Per-scan execution state, FTS5 search, durable task leases.    | yes     |
| `data/skills.db` + `data/skills/`               | Skill library             | Skills DB and on-disk skill files (LICENSE, SKILL.md, refs).   | yes     |
| `.agents/skills/`                               | Skill ingestion           | Source-of-truth skill library (read on boot via `ingest_skills`). | yes  |
| `reports/`                                      | Reporting                 | Generated PDF / SARIF / STIX / JSON reports per scan.          | optional |
| `logs/`                                         | Backend                   | Runtime logs.                                                  | optional |
| `brain/`                                        | Recon ingestion           | Legacy memory store (`brain/memory.json`) — append-only.       | yes     |
| `data/scan_output/` (or recon container scan dir) | TerminalEngine          | Raw tool output captured by the Docker backend.                | optional |

For Docker Compose:

- The backend container mounts `scan_states/`, `data/`, `reports/`,
  `logs/`, `.agents/`, and `brain/` as named volumes.
- The recon container mounts `/scan` (RW) and `/tools` (RO) — see
  `docker/recon/README.md` for the host paths and the
  `docker/recon/Dockerfile` for the container layout.
- Redis can be ephemeral if you accept losing the idempotency cache
  on restart; back it up if you care about the discovery dedupe
  history.

## 4. Ports

| Port  | Service          | Bound                | Notes                                 |
| ----- | ---------------- | -------------------- | ------------------------------------- |
| 8000  | Backend HTTP/WS  | `127.0.0.1` by default | Bind to `0.0.0.0` only behind Nginx.  |
| 6379  | Redis            | `127.0.0.1`          | Local-only unless cluster mode.       |
| 9867  | PinchTab         | `127.0.0.1`          | Override via `PINCHTAB_BASE_URL`.     |
| (none) | OpenClaw         | in-process           | Talks to Chromium over CDP.           |
| (none) | Recon container  | docker exec          | No published port; backend uses `docker exec` (`running_recon_container()`). |

## 5. Scaling notes

- The single-process `serve` mode is fine through ~100 concurrent
  scans on an 8-core box. Past that, switch to `cluster` mode or
  run an explicit `master` + N `worker` pair backed by Redis (see
  `backend/main.py:332`, `DistributedAttackCluster`).
- `MAX_CONCURRENT_LEARNING` and `EVENT_BATCH_SIZE` are the two knobs
  that matter for the coordinator under load. Bump batch size before
  bumping concurrency — the learning engine writes are the
  bottleneck.
- The recon container itself can be sized independently. One
  recon container per backend is the simplest topology; share a
  container across backends only if scan IDs are unique cluster-wide
  (they are — `HIVE-V5-<10hex>`).
- Browser memory grows with active contexts. `BrowserHealthMonitorExtension`
  alerts at 1 GB per agent (`backend/core/agent_health_monitor.py:667`);
  size containers / pods accordingly.
