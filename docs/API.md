# Vigilagent — API Reference

> Every public endpoint registered in `backend/main.py` (and the additional
> `/api/v1/recon` router under `backend/agents/alpha_recon/api_routes.py`).
> Each entry cites the file + line where it's declared. Endpoints flagged
> **§22** are the spec‑defined primary scan API; everything else is the
> additive surface that already existed.

---

## 1. Conventions

- **Base URL.** Defaults to `http://127.0.0.1:8000` in dev. The frontend
  resolves it via `VITE_API_BASE_URL` or auto‑derives from
  `window.location` (`src/lib/api.js:1-23`).
- **Content type.** All bodies are `application/json` unless noted.
- **Errors.** Validation failures return HTTP 400 with `{ "detail": "…" }`
  except for `POST /api/attack/fire`, which returns HTTP 422 with the
  Pydantic error list (`backend/main.py:155-161`).
- **Auth.** Most endpoints are unauthenticated in dev. `POST /api/dashboard/*`
  routes use rate‑limit + CSRF decorators (`backend/api/endpoints/dashboard.py`).
  WebSockets enforce 2FA tokens **only when** `enabled: true` in
  `user_config.json` (`backend/main.py:266-281`).
- **Rate limiting.** Routes wrapped with `@rate_limit(...)` are throttled by
  `backend/core/rate_limiter.py` — the cleanup task is started in
  `lifespan` (`backend/main.py:90`).

---

## 2. Health & inventory

### `GET /api/health`

- **Source.** `backend/main.py:171-198`.
- **Description.** Production health probe; tests Supabase, Redis, and
  reports the Alpha v6 flag.
- **Response (200).**

  ```json
  {
    "status": "healthy" | "degraded",
    "version": "v6.1-omega",
    "latency_ms": 12.3,
    "components": {
      "supabase": "healthy" | "not_configured" | "unhealthy",
      "redis":    "healthy" | "not_configured" | "unhealthy",
      "alpha":    "enabled" | "disabled"
    },
    "spy_connected": false,
    "extensions_active": 0
  }
  ```

- **Errors.** None — degrades gracefully.

### `GET /api/tools`

- **Source.** `backend/main.py:201-217`.
- **Description.** Recon tool inventory + availability check
  (Architecture §7, §22). Drives the New Scan UI's "what's installed".
- **Response.**

  ```json
  {
    "tools": [
      { "name": "subfinder", "phase": "passive_intelligence",
        "binary": "subfinder", "modes": ["PASSIVE_ONLY", "STANDARD", "AGGRESSIVE"],
        "installed": true, "source": "path", "reason": "" }
    ],
    "total": 39,
    "installed": 17
  }
  ```

---

## 3. Scans (primary API — §22)

Mounted at `/api/scans`. **Source:** `backend/api/endpoints/scans.py:1`.

### `POST /api/scans` — Create scan **(§22)**

- **Source.** `scans.py:42-67`.
- **Request.**

  ```json
  {
    "target_url": "https://example.com",
    "mode": "STANDARD",
    "modules": ["The Tycoon", "SQL Injection Probe"],
    "scan_id": null
  }
  ```

  - `target_url` (required) — string.
  - `mode` — defaults to `"STANDARD"`. Other values: `AGGRESSIVE`,
    `PASSIVE_ONLY`.
  - `modules` — optional UI module list. Empty = run all.
  - `scan_id` — optional override. When omitted, auto‑generated as
    `HIVE-V5-<10hex>`.

- **Response (202 Accepted).**

  ```json
  { "scan_id": "HIVE-V5-abc123def4", "status": "accepted" }
  ```

- **Errors.** Validation → 400 `{detail}`.

### `GET /api/scans` — List scans **(§22)**

- **Source.** `scans.py:71-122`.
- **Response.**

  ```json
  {
    "scans": [
      { "id": "HIVE-V5-…", "target": "https://…", "target_url": "https://…",
        "status": "Running", "report_ready": false,
        "created_at": "2026-01-01T00:00:00" }
    ],
    "count": 1
  }
  ```

  Sorted newest‑first by `created_at`. Empty timestamps sort last.

### `GET /api/scans/{scan_id}` — Scan detail **(§22)**

- **Source.** `scans.py:125-128`.
- **Response.** The full scan record from `StateManager` (target, status,
  modules, results, events, …).
- **Errors.** 404 when `scan_id` is unknown.

### `POST /api/scans/{scan_id}/{pause|resume|cancel}` — Lifecycle **(§22)**

- **Source.** `scans.py:131-172`.
- **Behaviour.** Sets the scan status (`Paused` / `Running` / `Cancelled`)
  in `StateManager` and publishes a `CONTROL_SIGNAL` event
  (`THROTTLE` / `RESUME` / `ABORT`) to the live bus.
- **Response.**

  ```json
  { "scan_id": "…", "signal": "THROTTLE" | "RESUME" | "ABORT",
    "delivered": true }
  ```

  `delivered: false` means there was no live agent bus to publish to (the
  status update was still applied).

### `GET /api/scans/{scan_id}/events` — Event transcript **(§22)**

- **Source.** `scans.py:175-180`.
- **Query.** `limit=500` (default). Returns the last `limit` events.
- **Response.**

  ```json
  { "scan_id": "…", "events": [...], "count": 1234 }
  ```

### `GET /api/scans/{scan_id}/findings` — Confirmed findings **(§22)**

- **Source.** `scans.py:301-307`. Merges `scan["results"]`,
  `scan["findings"]`, and the `VULN_CONFIRMED` events buffer (see
  `_findings_from_scan` at `scans.py:182-227`); each is enriched via
  `_enrich_finding_for_api` (`scans.py:230-298`).
- **Response.**

  ```json
  {
    "scan_id": "…",
    "findings": [
      { "id": "F-…", "type": "SQL_INJECTION", "severity": "HIGH",
        "url": "https://…/path?id=1", "cvss_score": 8.6,
        "cvss_severity": "HIGH",
        "evidence": { "request": "...", "response": "..." },
        "remediation": "Validate and parameterise…",
        "agent": "agent_gamma", "timestamp": "..." }
    ],
    "count": 12
  }
  ```

### `GET /api/scans/{scan_id}/graph` — Knowledge graph **(§22)**

- **Source.** `scans.py:310-316`.
- **Description.** Stats + snapshot from
  `unified_knowledge_graph.stats()`.
- **Response.** Implementation‑defined dict (node/edge counts, last update).

### `GET /api/scans/{scan_id}/report` — Report links **(§22)**

- **Source.** `scans.py:319-333`.
- **Response.**

  ```json
  {
    "scan_id": "…",
    "reports": {
      "pdf": "/api/reports/download/Scan_Report_<id>.pdf",
      "json": "<reports_dir>/<id>/findings.json"
    },
    "export_endpoint": "/api/reports/findings/<id>/export"
  }
  ```

  Keys are present only if the file exists on disk.

---

## 4. Legacy attack surface

### `POST /api/attack/fire`

- **Source.** `backend/api/endpoints/attack.py:31-117`.
- **Predates §22** but kept for backward compat.
- **Request (`AttackPayload`, `backend/schemas/payloads.py:21`).**

  ```json
  {
    "target_url": "https://…",
    "method": "POST",
    "headers": { "x-trace": "abc" },
    "body": "{\"id\":1}",
    "velocity": 50,
    "concurrency": 50,
    "rps": 100,
    "modules": ["The Tycoon"],
    "filters": [],
    "duration": 600
  }
  ```

- **Response.**

  ```json
  {
    "status": "Swarm Online",
    "scan_id": "<uuid4>",
    "message": "The Singularity has been unleashed. Monitor the 'Live Graph'…"
  }
  ```

- **Errors.**
  - 422 on Pydantic validation (per `backend/main.py:155-161`).
  - 403 on out‑of‑scope target URL (SSRF allowlist).
  - 429 if a scan for `(method, target_url)` is already running.

### `POST /api/attack/replay/{vuln_id}`

- **Source.** `backend/api/endpoints/attack.py:120-`.
- **Description.** Replay a recorded attack against `vuln_id` to verify
  remediation.
- **Errors.** 404 if `vuln_id` is unknown.

---

## 5. Recon ingestion (legacy)

Mounted at `/api/recon`. **Source:** `backend/api/endpoints/recon.py:1`.

### `POST /api/recon/ingest`

- **Source.** `recon.py:42-103`.
- **Request (`ReconPayload`, `backend/schemas/payloads.py:4`).**

  ```json
  { "url": "...", "method": "GET", "headers": {}, "body": null,
    "timestamp": 1700000000.0 }
  ```

- **Response.** `{"status": "ingested"}`.
- **Side effects.** Updates RPS gauge, broadcasts a `RECON_PACKET`
  WebSocket frame, and (when the request was tagged with the legacy
  scanner header) appends to `brain/memory.json`.

### `GET /api/recon/keyring`

- **Source.** `recon.py:104-112`.
- **Response.** Contents of `keyring.json`. Empty list if the file is
  missing.

### `POST /api/recon/keys`

- **Source.** `recon.py:113-`.
- **Description.** Append a per‑URL key entry. Validated through
  `backend/core/url_validator.py` to prevent SSRF.
- **Errors.** 400 on invalid URL.

---

## 6. Reports

Mounted at `/api/reports`. **Source:** `backend/api/endpoints/reports.py:1`.

| Method | Path | Source | Description |
| --- | --- | --- | --- |
| `GET` | `/api/reports/download/{filename}` | `reports.py:15-` | Download a generated PDF/JSON file. |
| `GET` | `/api/reports/` | `reports.py:88-` | List PDF reports. |
| `GET` | `/api/reports/pdf/{scan_id}` | `reports.py:99-` | On‑demand render. Rate‑limited. |
| `GET` | `/api/reports/consolidated` | `reports.py:176-` | Aggregate report across recent scans. |
| `GET` | `/api/reports/diff/{scan_id_1}/{scan_id_2}` | `reports.py:274-` | Scan diff engine. |
| `GET` | `/api/reports/live/{scan_id}` | `reports.py:337-` | Incremental report payload for live UI. |
| `POST` | `/api/reports/findings/{scan_id}/export` | `reports.py:69-` | Export evidence‑first formats (SARIF/STIX/JSON/Markdown). |

**Response shape (`/api/reports/findings/{id}/export`).**

```json
{
  "scan_id": "…",
  "finding_count": 8,
  "outputs": { "sarif": "...path...", "stix": "...path...", "json": "..." }
}
```

---

## 7. Defense

Mounted at `/api/defense`. **Source:** `backend/api/defense.py:1`.

| Method | Path | Source | Notes |
| --- | --- | --- | --- |
| `GET` | `/api/defense/analyze` | `defense.py:23-27` | Capability probe (TC005). |
| `POST` | `/api/defense/analyze` | `defense.py:28-` | Analyse a request for injection / anomaly. |

---

## 8. Dashboard, settings, auth

Mounted at `/api/dashboard`. **Source:** `backend/api/endpoints/dashboard.py`.
Routes use `@rate_limit()` and many enforce `@csrf_protect()`.

### Public dashboard

| Method | Path | Source | Description |
| --- | --- | --- | --- |
| `GET` | `/api/dashboard/stats` | `:208` | Cached aggregate metrics. |
| `GET` | `/api/dashboard/scans` | `:268` | Scan list view (legacy). |
| `GET` | `/api/dashboard/settings` | `:290` | Read settings. |
| `POST` | `/api/dashboard/settings` | `:284` | Update settings (CSRF). |
| `GET` | `/api/dashboard/csrf-token` | `:299` | Issue a CSRF token. |
| `POST` | `/api/dashboard/reset` | `:439` | Reset dashboard counters (CSRF). |

### 2FA + auth

| Method | Path | Source | Description |
| --- | --- | --- | --- |
| `POST` | `/api/dashboard/settings/2fa/generate` | `:309` | Generate a TOTP secret. |
| `POST` | `/api/dashboard/settings/2fa/verify` | `:345` | Verify code (CSRF). |
| `POST` | `/api/dashboard/settings/2fa/disable` | `:369` | Disable 2FA (CSRF). |
| `GET` | `/api/dashboard/auth/status` | `:392` | Whether 2FA is required + session state. |
| `POST` | `/api/dashboard/auth/login` | `:402` | Login (with optional TOTP). |
| `POST` | `/api/dashboard/auth/logout` | `:434` | Clear session. |

### Learning + evolution metrics (additive)

| Method | Path | Source |
| --- | --- | --- |
| `GET` | `/api/dashboard/api/learning/metrics` | `:451` |
| `GET` | `/api/dashboard/api/learning/patterns` | `:505` |
| `GET` | `/api/dashboard/api/learning/recommendations/{target_url:path}` | `:555` |
| `GET` | `/api/dashboard/api/evolution/health` | `:590` |
| `GET` | `/api/dashboard/api/evolution/health/{agent_name}` | `:616` |
| `GET` | `/api/dashboard/api/evolution/healing` | `:646` |
| `GET` | `/api/dashboard/api/evolution/healing/{agent_name}` | `:669` |
| `GET` | `/api/dashboard/api/evolution/skills` | `:690` |
| `GET` | `/api/dashboard/api/evolution/skills/top` | `:733` |
| `GET` | `/api/dashboard/api/evolution/skills/{skill_id}` | `:757` |
| `GET` | `/api/dashboard/api/evolution/skills/stats` | `:784` |
| `POST` | `/api/dashboard/api/evolution/skills/extract` | `:804` |
| `GET` | `/api/dashboard/api/evolution/metrics` | `:841` |
| `GET` | `/api/dashboard/api/integration/metrics` | `:882` |
| `GET` | `/api/dashboard/api/integration/realtime` | `:951` |
| `GET` | `/api/dashboard/api/integration/drilldown/{metric_type}` | `:1013` |

> **Note.** These are *additive*. They are NOT documented in the §22 spec
> and may evolve. The frontend treats them as non‑critical telemetry
> sources.

---

## 9. AI control plane

Mounted at `/api/ai`. **Source:** `backend/api/endpoints/ai.py:1`.

| Method | Path | Source | Description |
| --- | --- | --- | --- |
| `POST` | `/api/ai/mutate` | `:21` | Generate payload variants from base + logic vectors. |
| `POST` | `/api/ai/autonomous/engage` | `:50` | Kick off an autonomous mutation campaign. |
| `GET` | `/api/ai/status` | `:66` | LLM availability + counters. |

Mounted at `/api/runtime` (NEW — additive, not in original §22 spec).
**Source:** `backend/api/endpoints/runtime.py:1`.

| Method | Path | Source | Description |
| --- | --- | --- | --- |
| `GET` | `/api/runtime/tools` | `:23` | Tool registry schemas. |
| `POST` | `/api/runtime/tools/run` | `:28` | Execute a registered tool. |
| `GET` | `/api/runtime/approvals` | `:40` | Pending approval tickets (optional `scan_id`). |
| `POST` | `/api/runtime/approvals/{approval_id}/approve` | `:45` | Approve a ticket. |
| `POST` | `/api/runtime/approvals/{approval_id}/deny` | `:53` | Deny a ticket. |
| `GET` | `/api/runtime/graph` | `:61` | Knowledge graph stats. |
| `GET` | `/api/runtime/telemetry` | `:66` | Recent telemetry spans. |
| `GET` | `/api/runtime/self-improvement` | `:71` | Auditable agent‑evolution log. |
| `GET` | `/api/runtime/scope` | `:82` | Engagement scope + auth state. |
| `GET` | `/api/runtime/terminal` | `:89` | TerminalEngine telemetry (Architecture §8). |
| `GET` | `/api/runtime/recovery` | `:96` | Recovery / healing engine metrics. |

---

## 10. Skills catalogue

Mounted at `/api/skills`. **Source:** `backend/api/endpoints/skills.py:1`.

| Method | Path | Source | Description |
| --- | --- | --- | --- |
| `GET` | `/api/skills/` | `:19` | List skills (filter by `domain`, `agent`, `risk`). |
| `GET` | `/api/skills/stats` | `:44` | Catalog statistics. |
| `GET` | `/api/skills/{skill_id}` | `:54` | Single skill metadata. |
| `POST` | `/api/skills/reload` | `:67` | Re‑ingest from disk (Architecture §5.3.1). |

---

## 11. Self‑awareness (introspection)

Mounted at `/api/self-awareness`. **Source:**
`backend/api/endpoints/self_awareness.py:1`.

| Method | Path | Source |
| --- | --- | --- |
| `GET` | `/api/self-awareness/` | `:31` |
| `GET` | `/api/self-awareness/agents/{agent_id}/performance` | `:76` |
| `GET` | `/api/self-awareness/agents/metrics/summary` | `:160` |
| `GET` | `/api/self-awareness/agents/{agent_id}/proficiency` | `:243` |
| `GET` | `/api/self-awareness/agents/{agent_id}/decisions` | `:318` |
| `GET` | `/api/self-awareness/findings/{finding_id}/audit-trail` | `:421` |
| `GET` | `/api/self-awareness/agents/coordination/status` | `:484` |
| `GET` | `/api/self-awareness/agents/{agent_id}/delegations` | `:545` |
| `GET` | `/api/self-awareness/agents/omega/meta-awareness` | `:625` |

> Marked **additive** (not in the §22 spec).

---

## 12. Code analysis

Mounted at `/api`. **Source:** `backend/api/endpoints/code_analysis.py:1`.

| Method | Path | Source | Description |
| --- | --- | --- | --- |
| `POST` | `/api/analyze-code` | `:25` | Static analysis of source code. |
| `POST` | `/api/analyze-iac` | `:42` | IaC misconfig scanner. |
| `POST` | `/api/analyze-dependencies` | `:52` | SBOM / dependency analysis. |

---

## 13. Data (per‑item RLS)

Mounted at `/api/data`. **Source:** `backend/api/endpoints/data.py:1`.

| Method | Path | Source | Description |
| --- | --- | --- | --- |
| `GET` | `/api/data` | `:24` | List items. |
| `POST` | `/api/data` | `:31` | Upsert. |
| `GET` | `/api/data/{item_id}` | `:52` | Get (RLS via `X-User-Id`). |
| `PUT` | `/api/data/{item_id}` | `:65` | Update (RLS). |
| `DELETE` | `/api/data/{item_id}` | `:78` | Delete (RLS). |

---

## 14. Bridge for the Chrome extension

Mounted at `/bridge`. **Source:** `backend/api/endpoints/bridge.py:1`. Each
endpoint ingests one capture class allowed by `scope_guard`.

| Method | Path | Source | Capture class |
| --- | --- | --- | --- |
| `POST` | `/bridge/session` | `:96` | session |
| `POST` | `/bridge/token` | `:101` | token |
| `POST` | `/bridge/traffic` | `:106` | traffic |
| `POST` | `/bridge/dom` | `:111` | dom |
| `POST` | `/bridge/storage` | `:116` | storage |
| `POST` | `/bridge/ws` | `:121` | ws |
| `GET` | `/bridge/commands` | `:126` | Approved instructions for the extension. |

The extension is passive; it never receives an instruction it didn't ask for.

---

## 15. Alpha Recon v6 (additive)

Mounted at `/api/v1/recon`. **Source:**
`backend/agents/alpha_recon/api_routes.py:28`.

| Method | Path | Source | Description |
| --- | --- | --- | --- |
| `POST` | `/api/v1/recon/start` | `:64` | Start a recon scan. |
| `GET` | `/api/v1/recon/status/{scan_id}` | `:91` | Current status. |
| `POST` | `/api/v1/recon/stop/{scan_id}` | `:110` | Stop a running scan. |
| `GET` | `/api/v1/recon/scans` | `:120` | List recent recon scans. |
| `GET` | `/api/v1/recon/entities/{scan_id}` | `:128` | Entities for a scan. |
| `GET` | `/api/v1/recon/relationships/{scan_id}` | `:136` | Entity edges. |
| `POST` | `/api/v1/recon/export` | `:144` | Export (SARIF/STIX/Markdown/Neo4j/Maltego/HackerOne). |

`StartReconRequest` (`api_routes.py:33-40`):

```json
{
  "target_url": "https://example.com",
  "mode": "STANDARD",
  "scan_id": "",
  "enable_pinchtab": true,
  "enable_external_tools": false,
  "phases": []
}
```

---

## 16. WebSocket endpoints

Both endpoints share the same handler (`backend/main.py:263-281`).

### `/stream` and `/ws/live`

- **Query.**
  - `client_type` — `"ui"` (default) or `"spy"`.
  - `token` — required when 2FA is enabled in `user_config.json`.
- **Behaviour.**
  - `manager.connect(websocket, client_type)` registers the connection.
  - Late‑joining UI clients receive a replay of the last 50 broadcasts
    (excluding `SPY_STATUS`).
  - The server pushes JSON frames batched at ~50 FPS; critical control
    events bypass the batcher via `broadcast_immediate`.
- **Frame vocabulary.** See `DATA_FLOW.md` §4.

---

## 17. What's spec‑documented vs additive

The §22 frontend contract covers **only** these:

- `POST /api/scans`, `GET /api/scans`, `GET /api/scans/{id}`
- `POST /api/scans/{id}/{pause|resume|cancel}`
- `GET /api/scans/{id}/{events|findings|graph|report}`
- `GET /api/health`, `GET /api/tools`
- `/api/reports/*` (download + export)

Every other endpoint listed in this doc is **additive** — present in the
running codebase but not part of the §22 frontend contract. They evolve
with the agent fleet and may change shape between releases. Treat them as
operator/diagnostic tools, not as a public API.

---

## 17a. Deep System Integration endpoints

The Deep System Integration coordinator (Architecture appendix
"Integration Coordinator") routes events between the Evolution stack and
the OpenClaw / PinchTab browser stack. The endpoints below expose its
runtime state and the one-shot skill-library migration that v2 introduced.
All three are **additive** — they live outside the §22 contract and are
treated by the UI as operator/diagnostic tools.

### `GET /api/integration/metrics`

- **Source.** `backend/api/endpoints/dashboard.py:882` →
  `IntegrationCoordinator.get_integration_metrics()`
  (`backend/core/integration_coordinator.py:284`).
- **Description.** Coordinator health snapshot. Aggregates the per-event
  counters, the per-dependency circuit-breaker trips, and the active
  feature-flag matrix into a single payload. Safe to poll from a
  dashboard at 10–30 s cadence.
- **Auth.** None in dev. Same surface as the rest of `/api/dashboard/*`.
- **Query params.** None.
- **Response (200).**

  ```json
  {
    "timestamp": 1716724800.123,
    "integration": {
      "events_processed": 1240,
      "events_failed": 7,
      "events_skipped": 88,
      "failure_rate": 0.00564,
      "circuit_breaker_trips": 0,
      "pending_discoveries": 3,
      "batches_flushed": 41,
      "last_batch_size": 12,
      "features_enabled": {
        "browser_learning": true,
        "cross_system_healing": false,
        "forensic_learning": false,
        "intelligent_routing": false
      }
    },
    "learning": { "total_patterns": 312, "http_patterns": 240, "browser_patterns": 72 },
    "skills":   { "total_skills": 187, "http_skills": 121, "browser_skills": 38, "hybrid_skills": 28 },
    "health":   { "total_agents": 11, "healthy_agents": 10, "unhealthy_agents": 0, "avg_health_score": 92.4 },
    "performance": { "...": "see backend/core/performance_optimizer.py" }
  }
  ```

  Field semantics for `integration`:

  - `events_processed` / `events_failed` — terminal counters since
    coordinator init. `events_skipped` covers events dropped by the
    rollout-percentage gate.
  - `failure_rate` = `events_failed / max(events_processed, 1)`.
  - `circuit_breaker_trips` — sum across the
    `browser_vulnerability_learning` and `discovery_learning` breakers.
    Any non-zero value means the coordinator has tripped at least once
    and degraded gracefully.
  - `pending_discoveries` — depth of the unflushed `BROWSER_DISCOVERY`
    batch.
  - `features_enabled` — current state of the four feature flags from
    `IntegrationConfig`.

- **Errors.** `500` with `{"error": "..."}` if any subsystem (coordinator,
  learning engine, skill library, health monitor) raises during the
  snapshot. The handler does not partially-fail — operators read the
  string and chase the failing subsystem.

### `GET /api/runtime/health`

- **Source.** `backend/api/endpoints/runtime.py:97` (`runtime_health`).
- **Description.** Live runtime status for the Live Monitor sidebar.
  Polled every ~10 s by the UI.
- **Auth.** None.
- **Query params.** None.

The response keeps its existing top-level shape (`browser`, `active_scans`,
`total_scans`, `agents`, `alerts`). Deep-integration deployments append a
`browser_health` sub-field carrying the per-agent browser metrics
collected by `BrowserHealthMonitorExtension`
(`backend/core/agent_health_monitor.py:684-729`).

- **Response (200), abridged.**

  ```json
  {
    "browser": {
      "openclaw": "healthy" | "unavailable",
      "pinchtab": "healthy" | "unavailable",
      "reasons": { "openclaw": "...", "pinchtab": "..." }
    },
    "browser_health": {
      "summary": {
        "total_agents": 3,
        "total_active_contexts": 5,
        "total_browser_memory_mb": 612.4,
        "avg_browser_health_score": 88.7,
        "browser_alerts": 0,
        "timestamp": 1716724800.123
      },
      "agents": {
        "agent_delta": {
          "active_contexts": 2,
          "context_memory_mb": 240.0,
          "page_load_time_ms": 612.0,
          "screenshot_time_ms": 80.0,
          "browser_error_rate": 0.01,
          "browser_health_score": 92.0
        }
      }
    },
    "active_scans": 1,
    "total_scans": 47,
    "agents":  { "...": "system health summary" },
    "alerts":  [ "...last 20..." ]
  }
  ```

  `browser_health.summary` mirrors
  `BrowserHealthMonitorExtension.get_browser_health_summary()`;
  `browser_health.agents` mirrors `get_all_browser_health()`. When the
  browser stack is offline, `browser_health` is omitted (the existing
  `browser.error` field surfaces the cause).

- **Errors.** Best-effort. Subsystem failures degrade the affected field
  only, never the whole call.

### `POST /api/skills/migrate-v2`

- **Source.** Planned migration kick (Architecture appendix "Integration
  Coordinator", task 5.10). Wraps
  `python -m backend.skills.migrations.v2_browser --apply` for one-shot
  invocation from the operator console.
- **Description.** Idempotent migration that re-shapes existing skills
  into the v2 BrowserSkill format: adds semver versions, capability
  requirements, and execution-context tags. Re-running on a migrated
  library is a no-op.
- **Auth.** **Required.** Same gate as
  `POST /api/dashboard/auth/login` — the request is rejected with
  `401 Unauthorized` when the dashboard session is unauthenticated and
  with `403 Forbidden` when 2FA is configured but the supplied TOTP is
  missing or invalid.
- **Query params.** None.
- **Request body.**

  ```json
  { "dry_run": false, "limit": null }
  ```

  - `dry_run` — when `true`, the migration runs in plan mode and reports
    the diff without writing. Defaults to `false`.
  - `limit` — optional cap on the number of skills processed in a single
    invocation; useful for canarying.

- **Response (200).**

  ```json
  {
    "status": "ok",
    "scanned": 187,
    "migrated": 154,
    "already_v2": 33,
    "failed": 0,
    "duration_ms": 1842
  }
  ```

- **Errors.**
  - `401` — no authenticated session.
  - `403` — 2FA required, no/invalid TOTP.
  - `409 Conflict` — a previous migration is still running (the migration
    holds a Redis lock; see `IntegrationConfig.lock_ttl_seconds`).
  - `500` — migration aborted mid-flight; response contains
    `{ "error": "...", "scanned": N, "migrated": M }` so the operator
    can see how far it got.

---

## 18. Evidence index

Quick links to the route declarations:

- `backend/main.py:163-261` — router registration.
- `backend/api/endpoints/scans.py` — primary scan API.
- `backend/api/endpoints/attack.py` — legacy attack surface.
- `backend/api/endpoints/recon.py` — recon ingestion.
- `backend/api/endpoints/reports.py` — reports.
- `backend/api/defense.py` — defense.
- `backend/api/endpoints/dashboard.py` — dashboard + auth + learning.
- `backend/api/endpoints/ai.py` — AI control plane.
- `backend/api/endpoints/runtime.py` — runtime telemetry/approvals.
- `backend/api/endpoints/skills.py` — skills catalogue.
- `backend/api/endpoints/self_awareness.py` — introspection.
- `backend/api/endpoints/code_analysis.py` — static analysis.
- `backend/api/endpoints/data.py` — per‑item RLS demo.
- `backend/api/endpoints/bridge.py` — extension bridge.
- `backend/agents/alpha_recon/api_routes.py` — Alpha Recon v6.
