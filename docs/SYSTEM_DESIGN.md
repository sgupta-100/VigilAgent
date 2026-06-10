# Vigilagent — System Design

> Companion to `ARCHITECTURE.md`. This document zooms into the components,
> the data‑flow contracts between them, the API surfaces they expose, the DB
> tables that back them, and the caching strategy that keeps the hot path
> fast.

---

## 1. Component map

```mermaid
graph TB
    subgraph Edge["Edge / Transport"]
        FE["React UI<br/>src/App.jsx"]
        FAPI["FastAPI app<br/>backend/main.py"]
        WSM["SocketManager<br/>backend/api/socket_manager.py"]
    end

    subgraph Control["Control Plane"]
        ORCH["HiveOrchestrator<br/>backend/core/orchestrator.py"]
        DELG["DelegationManager<br/>backend/core/delegation_manager.py"]
        PLAN["MissionPlanner<br/>backend/core/planner.py"]
        GATE["PhaseGate + EndpointTracker<br/>backend/core/phase_gate.py"]
    end

    subgraph Bus["Event Plane"]
        EB["EventBus<br/>backend/core/hive.py"]
        DEB["DistributedEventBus<br/>(Redis pub/sub overlay)"]
    end

    subgraph Agents["Agent Plane"]
        ALPHA["Alpha"]
        BETA["Beta"]
        GAMMA["Gamma"]
        SIGMA["Sigma"]
        OMEGA["Omega"]
        ZETA["Zeta"]
        KAPPA["Kappa"]
        PRISM["Prism"]
        CHI["Chi"]
        DELTA["Delta"]
        NETC["NetworkServiceCommander"]
    end

    subgraph Tools["Tool Plane"]
        TERM["TerminalEngine<br/>backend/core/terminal_engine.py"]
        REG["RECON_TOOLS registry<br/>backend/tools/recon/registry.py"]
        DOCK["Docker sandbox"]
        LOC["Local PATH"]
    end

    subgraph Persist["Persistence"]
        SQLT[("SQLite + WAL + FTS5<br/>scan_states/scan_state.db")]
        STATS[("StateManager / stats.json<br/>backend/core/state.py")]
        SUPA[("Supabase tables")]
        REDIS[("Redis hot cache + locks")]
    end

    subgraph Brain["Cortex / Brain"]
        CORT["CortexEngine<br/>backend/ai/cortex.py"]
        SKILL["SkillLibrary<br/>backend/core/skill_library.py"]
        KG["UnifiedKnowledgeGraph<br/>backend/core/unified_knowledge_graph.py"]
    end

    subgraph Reports["Reporting"]
        PDF["VigilagentReportBuilder<br/>backend/reporting/scan_pdf.py"]
        FIND["FindingReport (SARIF/STIX/JSON)"]
    end

    FE --> FAPI
    FE -.-> WSM
    FAPI --> ORCH
    ORCH --> EB
    EB --> DEB
    DEB --> REDIS
    ORCH --> DELG
    ORCH --> PLAN
    ORCH --> GATE
    EB --> Agents
    Agents --> EB
    Agents --> CORT
    Agents --> SKILL
    Agents --> KG
    Agents --> TERM
    TERM --> REG
    TERM --> DOCK
    TERM --> LOC
    ORCH --> SQLT
    ORCH --> STATS
    ORCH --> SUPA
    EB --> WSM
    Reports --> SUPA
    PDF --> FAPI
    KG --> SQLT
```

The control plane is intentionally thin: the Orchestrator doesn't *own* state,
it owns *lifecycle*. State lives in the persistence layer; reasoning lives in
agents; coordination is done by the EventBus and the DelegationManager.

---

## 2. Sequence — Create scan

```mermaid
sequenceDiagram
    autonumber
    participant UI as React UI
    participant API as FastAPI /api/scans
    participant ST as StateManager
    participant ORC as HiveOrchestrator
    participant BUS as EventBus
    participant AGT as Agents
    participant DB as ScanStateDB
    participant WS as SocketManager

    UI->>API: POST /api/scans { target_url, mode, modules }
    API->>API: build scan_id (HIVE-V5-<10hex>)
    API->>ST: register_scan(scan_record)
    API-->>UI: 202 { scan_id, status:"accepted" }
    API->>ORC: BackgroundTask: bootstrap_hive(target_config, scan_id)

    Note over ORC: lifecycle phase = Initializing
    ORC->>ST: register_scan / update_scan_status
    ORC->>BUS: choose EventBus | DistributedEventBus
    ORC->>BUS: subscribe global event_listener
    ORC->>AGT: instantiate + start core agents
    AGT-->>BUS: AGENT_STATUS{ status:"ONLINE" }
    BUS->>WS: broadcast LIVE_ATTACK_FEED (AGENT_ONLINE)
    WS-->>UI: WS frame { type:"LIVE_ATTACK_FEED" }

    ORC->>BUS: publish TARGET_ACQUIRED { url, scan_mode }
    AGT->>BUS: subscribers fan out
    Note over AGT: Alpha enters recon
    AGT-->>DB: scan_state_db.add_event / record_tool_run
    AGT-->>BUS: RECON_PACKET / VULN_CANDIDATE / VULN_CONFIRMED
    BUS->>WS: broadcast (LIVE_ATTACK_FEED, LIVE_THREAT_LOG, COVERAGE_UPDATE)
    WS-->>UI: stream frames
```

**Notes.**

- The `202` response is the contract surface — the UI must poll
  `GET /api/scans/{id}` or rely on the WebSocket stream for progress.
- `BackgroundTasks` is the right tool here because `bootstrap_hive` is a
  long‑running coroutine that must outlive the request lifecycle.
- The Orchestrator never returns; instead it broadcasts `SCAN_UPDATE`
  events the UI uses to advance state.

Source citations:

- `backend/api/endpoints/scans.py:42` — `create_scan`.
- `backend/core/orchestrator.py:78` — `bootstrap_hive`.
- `backend/api/socket_manager.py:175` — `_process_batch_queue`.

---

## 3. Sequence — Recon → Attack handoff

```mermaid
sequenceDiagram
    autonumber
    participant ORC as HiveOrchestrator
    participant ALPHA as Alpha (Recon)
    participant TE as TerminalEngine
    participant REG as RECON_TOOLS
    participant DOCK as Docker / Local
    participant BUS as EventBus
    participant DB as ScanStateDB
    participant SEED as AttackSurfaceSeeder
    participant SIG as Sigma
    participant BETA as Beta

    ORC->>ALPHA: TARGET_ACQUIRED
    ALPHA->>REG: pick tools by phase + mode
    loop for each phase (passive → DNS → HTTP → routes → API → visual → templates)
        ALPHA->>TE: run argv, scan_id, agent
        TE->>DOCK: exec (docker | local)
        DOCK-->>TE: stdout chunks
        TE->>BUS: stream_callback for live UI feed
        TE-->>ALPHA: TerminalResult
        ALPHA->>BUS: RECON_PACKET (each finding)
        ALPHA->>DB: record_tool_run (sha256, summary, duration_ms)
    end
    ALPHA->>BUS: RECON_COMPLETE (source=agent_alpha)
    Note over ORC: alpha_recon_complete.set() → release attack phase
    ORC->>SEED: seed_attack_surface(target, scan_id, recon_endpoints)
    SEED-->>ORC: SeededSurface{ targets, authenticated, principal }
    ORC->>BUS: PHASE_STARTED { phase:"ASSESSMENT" }
    loop for each module × seeded target
        ORC->>BUS: JOB_ASSIGNED (JobPacket)
        BUS->>SIG: dispatch (payload generation)
        BUS->>BETA: dispatch (exploitation)
        SIG->>BETA: derived payload via bus
        BETA-->>BUS: VULN_CANDIDATE → VULN_CONFIRMED
    end
```

**Why the timeout matters.**

`alpha_recon_complete` is an `asyncio.Event` that the recon completion handler
sets when Alpha emits `RECON_COMPLETE`. The orchestrator waits up to
`RECON_MAX_WAIT_SECONDS` (default 180) and then proceeds with whatever surface
recon produced (`backend/core/orchestrator.py:773-789`). This guarantees the
attack phase is never starved by a stalled recon stage.

**The seeder.**

`backend/core/attack_surface_seeder.seed_attack_surface` is the bridge
between recon discovery and exploitation: it picks param‑carrying URLs from
recon, optionally authenticates, and returns a `SeededSurface` whose
`targets` list is fed into every `JobPacket` (`orchestrator.py:828-840`). If
seeding fails, the attack pipeline still runs against the bare base URL.

---

## 4. Sequence — Exploit confirmation → PDF report

```mermaid
sequenceDiagram
    autonumber
    participant BETA as Beta
    participant GAMMA as Gamma
    participant BUS as EventBus
    participant GUARD as GuardLayer
    participant LISTEN as event_listener (Orchestrator)
    participant CVSS as CVSSCalculator
    participant DB as ScanStateDB
    participant SUPA as Supabase
    participant ST as StateManager
    participant WS as SocketManager
    participant UI as React UI
    participant PDF as VigilagentReportBuilder

    BETA-->>BUS: VULN_CANDIDATE { url, type, payload, evidence }
    GAMMA->>BUS: forensic verification → upgrades to VULN_CONFIRMED
    BUS->>LISTEN: VULN_CONFIRMED handler
    LISTEN->>GUARD: filter_single(real_payload)
    alt below evidence threshold
        GUARD-->>LISTEN: drop (≥2 signals required)
        LISTEN-->>BUS: log dropped finding
    else accepted
        LISTEN->>SUPA: db_manager.report_vulnerability(scan_id, …)
        LISTEN->>ST: stats_db_manager.record_finding (severity, sig_data)
        LISTEN->>CVSS: calculate base score + severity band
        LISTEN->>LISTEN: Bayesian fusion (gi5*0.35 + gamma*0.30 + cvss*0.35)
        LISTEN->>WS: VULN_UPDATE + LIVE_THREAT_LOG
        WS-->>UI: dashboard counters tick + threat row appended
    end

    Note over LISTEN,DB: Findings persist in three places: results, findings, events buffer.
    LISTEN->>DB: scan_state_db.add_event (durable)

    Note over BUS: Scan finalises → REPORT_READY emitted by orchestrator.
    LISTEN->>PDF: VigilagentReportBuilder(scan_id, target_url, events, telemetry, cortex).build()
    PDF->>PDF: collect_findings (dedupe by sha256 of url+type+payload)
    PDF->>PDF: enrich via Cortex (description, impact, remediation, code-fix)
    PDF->>PDF: render Executive Summary → Detailed Findings → Timeline
    PDF-->>BUS: REPORT_READY { id }
    WS-->>UI: { type:"REPORT_READY", payload:{ id } }
    UI->>API: GET /api/scans/{id}/report
    API-->>UI: { reports:{ pdf:"/api/reports/download/Scan_Report_<id>.pdf" } }
```

**Why three persistence layers.**

The `_findings_from_scan` helper at `backend/api/endpoints/scans.py:182` calls
out the rationale: confirmed findings appear in `scan["results"]`,
`scan["findings"]`, and the `scan["events"]` buffer at different points in the
lifecycle. The API merges all three and dedupes by `(url, type)` so the
frontend always sees every confirmed finding even mid‑scan.

**LLM is enrichment‑only.**

The PDF builder uses the LLM strictly for prose (description, impact,
remediation bullets, code‑fix). Real data — target, scan_id, CVSS,
HTTP request/response, timeline — comes from the events buffer
(`backend/reporting/scan_pdf.py:303` design rules block).

---

## 5. API contract design

The full enumeration is in `API.md`. The high‑level shape:

| Surface | Prefix | Notes |
| --- | --- | --- |
| **Primary scan API** | `/api/scans` | Architecture §22; documented contract. |
| **Legacy attack/recon API** | `/api/attack`, `/api/recon` | Pre‑existing; kept additively. |
| **Reporting** | `/api/reports` | PDF, consolidated, diff, live, exports. |
| **Dashboard + auth + 2FA** | `/api/dashboard` | Session, CSRF, learning, evolution metrics. |
| **AI control plane** | `/api/ai`, `/api/runtime` | Mutations, tool runs, approvals, telemetry. |
| **Skills catalogue** | `/api/skills` | Browse + reload skill library. |
| **Defense / self-awareness** | `/api/defense`, `/api/self-awareness` | Threat analysis + agent introspection. |
| **Code & data tools** | `/api/analyze-code`, `/api/data` | Static analysis + per‑item RLS demo. |
| **Bridge for the Chrome extension** | `/bridge/*` | Capture session/token/traffic/dom/storage/ws. |
| **Alpha Recon v6** | `/api/v1/recon` | Direct REST controls for the new recon spine. |

Two design choices worth highlighting:

- **POST /api/attack/fire** explicitly maps Pydantic 422s to RFC‑7231 422
  responses (`backend/main.py:155-161`) — every other validation error returns
  HTTP 400 with a `detail` string, because the legacy frontend depends on the
  difference.
- **WebSocket auth** is config‑gated: `enabled: true` in `user_config.json`
  flips the `/stream` and `/ws/live` endpoints into "require token" mode
  (`backend/main.py:266-281`).

---

## 6. DB schema design

See `DB_SCHEMA.md` for the table‑by‑table reference. The shape:

```mermaid
erDiagram
    SCANS ||--o{ EVENTS : "has"
    SCANS ||--o{ MESSAGES : "has"
    SCANS ||--o{ FINDINGS : "has"
    SCANS ||--o{ TASKS : "has"
    SCANS ||--o{ TOOL_RUNS : "has"
    SCANS ||--o{ CHECKPOINTS : "has"
    FINDINGS ||--o{ EVIDENCE : "supports"
    SCANS ||--o{ GRAPH_NODES : "captures"
    SCANS ||--o{ GRAPH_EDGES : "captures"
    SCANS ||--o{ APPROVALS : "gates"
    SCANS ||--o{ AGENT_RUNS : "tracks"
    SCANS ||--o{ SKILL_RUNS : "tracks"
    SCANS ||--o{ LEARNING_UPDATES : "emits"
    TASKS ||--o{ TASK_ATTEMPTS : "retries"
    SCANS }o--o{ SEARCH_INDEX : "FTS5"
```

**Two sources of truth.**

- **SQLite (`scan_state.db`)** — durable execution state. Survives restart;
  drives resume + checkpoints (`backend/core/scan_state_db.py:1`).
- **Supabase** — distributed intelligence. Survives across hosts; powers the
  cluster lock and the cross‑run knowledge layer
  (`backend/core/database.py:13`).

**Fallback.** When Supabase is not configured, `EliteDBManager` returns
`None`/`[]` from every helper; nothing crashes (`database.py:40-43`).

---

## 7. Caching strategy

Layered, with strict TTLs where data is observable in dashboards.

| Layer | What it caches | TTL | Why |
| --- | --- | --- | --- |
| Process‑local `_recent_events` set + FIFO | Event ids per scan | 1000 entries / unbounded time | Exact‑once dedupe inside `EventBus.publish` (`hive.py:175-188`). |
| Process‑local replay buffer | Last 50 broadcasts | drop after eviction | UX nicety for late‑joining UI WebSockets (`socket_manager.py:151`). |
| `_skill_rec_cache` per agent | `(target_url, classes) → list` | scan lifetime | Avoids hitting `skill_library` once per finding — see `agent_mixins.SkillRecallMixin` (`agent_mixins.py:43-100`). |
| `dashboard.py _stats_cache` | `/api/dashboard/stats` payload | 1‑2 s | Throttles polling; primary refresh is via WebSocket. |
| Redis "hot cache" | `vuln:<scan>:<endpoint>:<type>` signature | 1 hour | Suppresses redundant Supabase upserts (`database.py:71-83`). |
| Redis distributed locks | `lock:task:<task_id>`, `job_lock:<task_id>` | 10 min / 1 hour | Prevents duplicate work on cluster. |
| SocketManager batching | Outbound WS frames | 20 ms | Coalesces high‑RPS bursts into one frame. |

Two anti‑caching invariants:

1. **`should_emit` is permanently true.** The user wants every request shown
   live; no sampling at the WS layer (`socket_manager.py:24`).
2. **No per‑finding cache invalidation.** Findings are always re‑computed
   from the events buffer via `_findings_from_scan` so a mid‑scan reload
   never lies (`scans.py:182`).

---

## 8. Failure modes and recovery

| Failure | Detection | Recovery |
| --- | --- | --- |
| Subscriber raises | `_safe_execute` catches and logs (`hive.py:212`) | DLQ entry persisted; flushed via diagnostics. |
| Redis offline at boot | `DistributedEventBus.start` warning (`hive.py:283-291`) | Bus stays local; same code path as `serve` w/o Redis. |
| Redis offline mid‑run | publish exception caught (`hive.py:317-320`) | Local broadcast still happens; global sync skipped. |
| Supabase offline | All helpers short‑circuit on `if not self.supabase` | Returns `None`/`[]`; UI sees fewer cross‑run signals. |
| SQLite locked | `_write` retries with jitter (`scan_state_db.py:280-292`) | Up to 5 attempts; final raise propagates. |
| Recon stalls | `RECON_MAX_WAIT_SECONDS` upper bound (`orchestrator.py:777-789`) | Attack phase proceeds with degraded surface. |
| Tool not installed | `check_tool_availability` (`registry.py:74-100`) | `installed:false` returned to `/api/tools`; orchestrator skips. |
| Agent crashes | `recovery_engine.healing_engine.monitor_and_heal()` (`orchestrator.py:660-677`) | `restart_callback` re‑starts the agent and broadcasts `GI5_LOG`. |
| WebSocket peer dead | `_send_with_timeout` returns the connection on 1 s timeout (`socket_manager.py:166-173`) | Removed from `ui_connections` immediately. |

---

## 9. Concurrency primitives — at a glance

- **`asyncio.Queue`** — per `ScanContext` event queue. Backpressure is
  natural; subscribers run in series within a scan.
- **`asyncio.to_thread`** — every Supabase / blocking‑I/O call.
- **`asyncio.create_task`** — wrapped through `TaskManager` so shutdown
  cancels them cleanly (`backend/core/task_manager.py`).
- **`asyncio.Event`** — `alpha_recon_complete`
  (`orchestrator.py:271`); `is_cancelled` flag on `ScanContext`.
- **`asyncio.gather`** — used in `SocketManager._process_batch_queue` to send
  to all UI connections concurrently with `return_exceptions=True`.
- **`threading.RLock`** — protects SQLite writes inside `ScanStateDB._lock`
  (`scan_state_db.py:213`). Single‑process; no cross‑host contention.

---

## 10. Hot paths to watch

These sections are the ones a perf regression will show up in first:

1. **`EventBus.publish`** — runs the `_sanitize_event_payload` walker for
   every event. If you add new payload types, profile this first.
2. **`ScanStateDB.add_events_bulk`** — called in tight loops by the recon
   spine. Don't replace `executemany` with per‑row inserts.
3. **`SocketManager._process_batch_queue`** — 50 FPS WebSocket fan‑out. JSON
   serialisation happens once per tick; don't re‑serialise per connection.
4. **`VigilagentReportBuilder._enrich_findings`** — LLM calls per finding,
   bounded by `LLM_OVERALL_TIMEOUT = 600 s`. Adjust per‑call timeout if
   you add expensive prompts.
5. **`db_manager.report_vulnerability`** — Redis hot‑cache check before
   Supabase upsert; preserve that order.
