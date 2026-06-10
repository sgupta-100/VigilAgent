# Vigilagent — Clean Architecture Target

> **Status: design only.** This document describes the target shape we'd like
> the codebase to evolve toward. **Nothing in `backend/` or `src/` has been
> moved or renamed for this doc.** It's a roadmap, not a refactor PR.

---

## 1. Why a clean‑arch target?

The current layout is *organic*. It grew the way every working system grows:
features land in the file that already imports the right symbols. A few
properties of that organic growth are now showing up as friction:

- `backend/core/orchestrator.py` is 1300+ lines and mixes **lifecycle**,
  **business logic** (CVSS fusion, finding dedupe), **transport** (WebSocket
  fan‑out), and **persistence** (Supabase + SQLite + stats.json) inside a
  single function.
- `backend/api/endpoints/scans.py` has business logic for "where do findings
  live" (`_findings_from_scan`, `_enrich_finding_for_api`). That belongs in a
  use‑case, not in an HTTP controller.
- The same imports show up in many places: `from backend.core.state import
  stats_db_manager`, `from backend.core.database import db_manager`. They
  hard‑couple every consumer to a *singleton instance* of those stores.
- Tests have to spin up the FastAPI app to exercise scan creation, even when
  they only want to verify "given a target URL, the scan id has the right
  shape and the scan record is persisted".

The dependency rule we want is the standard clean‑arch one: **outer layers
depend on inner layers, never the other way around.**

```
  frameworks_drivers  ──┐
                        ▼
   interface_adapters ──┐
                        ▼
            use_cases ──┐
                        ▼
                 domain
```

Anything in `domain` knows nothing about FastAPI, SQLite, Supabase, asyncio,
or the wire format of a WebSocket frame. Anything in `use_cases` knows about
domain entities and abstract ports, but not about concrete adapters. The
adapter layer wires real Supabase / FastAPI / aiohttp implementations into
those ports. The frameworks layer is the ASGI app, the websocket batcher,
and the Playwright driver.

---

## 2. Proposed folder structure

This is what the repo would look like *if* we did the refactor today. The
left column shows what already exists; the right column shows the target
location.

```
backend/
├── domain/                                # NEW — pure domain
│   ├── entities/
│   │   ├── scan.py                       # Scan aggregate
│   │   ├── finding.py                    # Finding + Evidence value objects
│   │   ├── endpoint.py                   # Endpoint + EndpointStatus
│   │   ├── job_packet.py                 # JobPacket / TaskTarget VOs
│   │   └── event.py                      # HiveEvent VO (currently Pydantic)
│   ├── value_objects/
│   │   ├── severity.py                   # Severity enum + CVSS band mapping
│   │   ├── scope_policy.py               # ScopePolicy as a pure VO
│   │   └── phase.py                      # ScanPhase enum
│   └── policies/
│       ├── evidence_threshold.py         # ≥2-signal rule (§17)
│       ├── scope_authorization.py        # §9 active-action rule
│       └── two_llm_exclusivity.py        # §11 LLM allowlist
│
├── use_cases/                            # NEW — application services
│   ├── create_scan.py                    # POST /api/scans
│   ├── run_recon.py                      # Alpha-driven recon phase
│   ├── enrich_finding.py                 # CVSS + Bayesian fusion + remediation
│   ├── promote_finding.py                # Candidate → Confirmed
│   ├── generate_report.py                # PDF builder orchestration
│   ├── checkpoint_phase.py               # Safe boundary capture
│   └── resume_scan.py                    # From last safe checkpoint
│
├── interface_adapters/                   # currently spread across api/, core/
│   ├── controllers/
│   │   ├── scans_controller.py           # FastAPI routes for /api/scans
│   │   ├── reports_controller.py         # /api/reports
│   │   ├── recon_controller.py           # /api/recon
│   │   ├── attack_controller.py          # /api/attack
│   │   └── runtime_controller.py         # /api/runtime
│   ├── presenters/
│   │   ├── finding_presenter.py          # _enrich_finding_for_api
│   │   ├── scan_list_presenter.py        # _created_at + sort ordering
│   │   └── ws_frame_presenter.py         # HiveEvent → BATCH | LIVE_ATTACK_FEED
│   ├── repositories/
│   │   ├── scan_repository.py            # ScanRepository port + adapter
│   │   ├── finding_repository.py
│   │   ├── tool_run_repository.py
│   │   └── checkpoint_repository.py
│   ├── event_bus/
│   │   ├── event_bus_port.py             # IEventBus interface
│   │   ├── in_process_event_bus.py       # current EventBus
│   │   └── distributed_event_bus.py      # current DistributedEventBus
│   ├── ws/
│   │   └── socket_broadcaster.py         # current SocketManager
│   └── llm/
│       └── cortex_adapter.py             # CortexEngine wrapper
│
├── frameworks_drivers/                   # the outermost layer
│   ├── http/
│   │   └── fastapi_app.py                # current backend/main.py
│   ├── persistence/
│   │   ├── sqlite/
│   │   │   ├── scan_state_db.py          # current scan_state_db
│   │   │   └── stats_json_store.py       # current state.py
│   │   ├── supabase/
│   │   │   └── elite_db_manager.py       # current database.py
│   │   └── redis/
│   │       └── redis_client.py
│   ├── browser/
│   │   ├── openclaw_driver.py
│   │   ├── pinchtab_driver.py
│   │   └── browser_orchestrator.py
│   ├── tools/
│   │   ├── terminal_engine.py            # current terminal_engine.py
│   │   ├── docker_sandbox.py
│   │   └── recon_registry.py             # current registry.py
│   └── ai/
│       ├── cortex_engine.py              # current ai/cortex.py
│       └── skill_library.py              # current skill_library
│
├── agents/                               # stays where it is, but pure
│   ├── alpha.py …                        # all agents become USE-CASE consumers
│   └── _shared/agent_mixins.py
│
└── apps/
    ├── api_app.py                        # main entry — wires everything
    └── cluster_app.py                    # master/worker entry
```

### 2.1 Mapping table — current → target

| Current location | Target layer | Reason |
| --- | --- | --- |
| `backend/main.py:42` (`lifespan`) | `apps/api_app.py` | composition root |
| `backend/main.py:163` (route registration) | `interface_adapters/controllers/*` | thin routers |
| `backend/api/endpoints/scans.py:_findings_from_scan` | `use_cases/promote_finding.py` | merge logic is business |
| `backend/api/endpoints/scans.py:_enrich_finding_for_api` | `interface_adapters/presenters/finding_presenter.py` | presentation only |
| `backend/core/orchestrator.py:bootstrap_hive` | `use_cases/create_scan.py` + `use_cases/run_recon.py` | one use‑case per phase |
| `backend/core/orchestrator.py:event_listener` (CVSS fusion) | `use_cases/enrich_finding.py` | finding policy |
| `backend/core/scope.py` (`ScopePolicy`) | `domain/value_objects/scope_policy.py` | pure rule |
| `backend/core/hive.py:EventBus` | `interface_adapters/event_bus/in_process_event_bus.py` | infra adapter |
| `backend/core/hive.py:DistributedEventBus` | `interface_adapters/event_bus/distributed_event_bus.py` | infra adapter |
| `backend/api/socket_manager.py` | `interface_adapters/ws/socket_broadcaster.py` | UI adapter |
| `backend/core/scan_state_db.py` | `frameworks_drivers/persistence/sqlite/scan_state_db.py` + a `ScanRepository` port over it | concrete driver |
| `backend/core/database.py` | `frameworks_drivers/persistence/supabase/elite_db_manager.py` + ports | concrete driver |
| `backend/core/terminal_engine.py` | `frameworks_drivers/tools/terminal_engine.py` | external process driver |
| `backend/reporting/scan_pdf.py` | `use_cases/generate_report.py` (orchestration) + `frameworks_drivers/reporting/pdf_renderer.py` (FPDF) | split policy from rendering |

---

## 3. Domain entities

### 3.1 `Scan`

```python
@dataclass(frozen=True)
class ScanId:
    value: str   # invariant: matches "HIVE-V[5-9]-[0-9a-f]{6,16}" or recon_<n>

@dataclass
class Scan:
    id: ScanId
    target_url: str
    mode: str                    # "STANDARD" | "AGGRESSIVE" | "PASSIVE_ONLY"
    modules: list[str]
    phase: ScanPhase
    status: ScanStatus           # Initializing | Running | Paused | Completed | Failed
    authorized: bool
    created_at: datetime
    updated_at: datetime

    def transition(self, to: ScanStatus) -> "Scan":
        # invariant: Initializing -> Running -> {Paused | Completed | Failed}
        ...
```

`Scan` is currently a `dict` shuffled between `stats_db_manager`,
`scan_state_db`, and the JSON file. Promoting it to an entity would let
`use_cases/create_scan.py` enforce the status‑transition invariant in one
place.

### 3.2 `Finding`

```python
@dataclass
class Finding:
    id: FindingId
    scan_id: ScanId
    title: str
    vuln_type: str
    severity: Severity
    state: FindingState           # candidate | confirmed | promoted
    confidence: float
    asset_url: str
    cvss_score: float
    cvss_severity: str
    evidence: list[Evidence]
    remediation: str

    def is_confirmable(self, signal_count: int) -> bool:
        return self.state == FindingState.CANDIDATE and signal_count >= 2
```

Currently the finding shape lives in `scan["results"]`,
`scan["findings"]`, and `scan["events"]` in three different layouts (see
`backend/api/endpoints/scans.py:_coerce`). A single domain entity would
allow `_enrich_finding_for_api` to be a presenter, not a duct‑tape coercer.

### 3.3 `Endpoint`

```python
@dataclass
class Endpoint:
    url: str                          # canonicalised
    discovered_by: str                # agent name
    tested_by: list[str] = []
    is_vulnerable: bool = False
```

Currently embedded in `EndpointTracker`. Would be a value object the
tracker mutates by returning new instances.

### 3.4 `HiveEvent`

Already a Pydantic model (`backend/core/hive.py:39`); promoting it to a
frozen `@dataclass` in `domain/entities/event.py` would remove the FastAPI
dependency from anything that just needs to *describe* an event.

---

## 4. Use cases

A use case is a thin function that:

1. Takes domain inputs.
2. Calls **ports** (abstract interfaces) for I/O.
3. Applies a domain policy.
4. Returns a domain output.

### 4.1 `CreateScan`

```python
class CreateScan:
    def __init__(self,
                 scans: ScanRepository,
                 events: EventBusPort,
                 launch: LaunchScanPort):
        ...

    async def execute(self, target_url: str, mode: str,
                      modules: list[str]) -> ScanId:
        scan = Scan.new(target_url, mode, modules)
        await self.scans.upsert(scan)
        await self.events.publish(HiveEvent.target_acquired(scan))
        await self.launch.run_in_background(scan)
        return scan.id
```

Replaces `backend/api/endpoints/scans.py:create_scan` + the implicit
coupling to `BackgroundTasks`.

### 4.2 `RunRecon`

Owns the whole "for each phase, for each tool, dispatch and parse" loop
that today lives in Alpha. Calls `TerminalEnginePort` (a port over
`terminal_engine.py`).

### 4.3 `EnrichFinding`

The current logic at `backend/core/orchestrator.py:340-378` belongs here.
Inputs: a `Finding` + the GuardLayer signal count. Outputs: a `Finding`
with CVSS + Bayesian fusion fields populated. No knowledge of WebSocket or
Supabase.

### 4.4 `GenerateReport`

Wraps `VigilagentReportBuilder.build` behind a port. Takes a `ScanId`,
returns a `ReportArtifact { path, format }`. The PDF rendering itself
stays in `frameworks_drivers`.

### 4.5 `CheckpointPhase` / `ResumeScan`

Already conceptually present in `scan_state_db.checkpoint_phase` /
`resume`. Would become use cases that consume a `CheckpointRepository`.

---

## 5. Ports (interface‑adapter contracts)

```python
# domain ports
class ScanRepository(Protocol):
    async def upsert(self, scan: Scan) -> None: ...
    async def get(self, scan_id: ScanId) -> Scan | None: ...
    async def list_recent(self, limit: int = 50) -> list[Scan]: ...

class FindingRepository(Protocol):
    async def add(self, finding: Finding) -> None: ...
    async def list_for_scan(self, scan_id: ScanId) -> list[Finding]: ...

class EventBusPort(Protocol):
    async def publish(self, event: HiveEvent) -> None: ...
    def subscribe(self, type: EventType, handler: Callable) -> None: ...

class SocketBroadcaster(Protocol):
    async def broadcast(self, frame: dict) -> None: ...
    async def broadcast_immediate(self, frame: dict) -> None: ...

class TerminalEnginePort(Protocol):
    async def run(self, argv: list[str], scan_id: ScanId,
                  agent: str, *, timeout: int = 180) -> TerminalResult: ...

class LLMPort(Protocol):
    async def generate_vulnerability_summary(self, vuln_type: str,
                                             payload: str, url: str) -> dict: ...
    async def generate_remediation_code(self, vuln_type: str,
                                        tech_stack: str) -> str: ...
```

The current code calls into singletons (`stats_db_manager`, `db_manager`,
`manager`, `terminal_engine`, `cortex`). Each singleton would gain a
matching port; the singletons become the default *implementation*, not the
*type*.

---

## 6. Wiring at the composition root

```python
# apps/api_app.py — the only place that knows about every layer
def build_app() -> FastAPI:
    sqlite = ScanStateDB()                           # driver
    stats = StatsJsonStore()                         # driver
    supabase = EliteDBManager()                      # driver
    redis = RedisClient(settings.REDIS_URL)          # driver
    bus = (DistributedEventBus(redis) if redis.url
           else InProcessEventBus())                 # adapter
    ws = SocketBroadcaster()                         # adapter
    cortex = CortexAdapter(get_cortex_engine())      # adapter
    terminal = TerminalEngineAdapter(terminal_engine)

    scan_repo = ScanRepoSqlite(sqlite, stats)        # adapter
    finding_repo = FindingRepoSqlite(sqlite, supabase)
    checkpoint_repo = CheckpointRepoSqlite(sqlite)

    create_scan = CreateScan(scan_repo, bus, LaunchScan(bus, terminal))
    enrich = EnrichFinding(finding_repo, GuardLayer(), CVSSCalculator())
    generate_report = GenerateReport(scan_repo, finding_repo, cortex,
                                     PdfRenderer())

    app = FastAPI(lifespan=lifespan_for(bus, sqlite, supabase, redis))
    register_scans_controller(app, create_scan, scan_repo)
    register_reports_controller(app, generate_report)
    # …
    return app
```

This is where the tradeoff bites: today the system has *one* implicit
composition root (the import‑side‑effects in `backend/main.py`). The
target makes it explicit and testable.

---

## 7. Migration roadmap (does NOT break existing code)

The order matters. Each step is shippable on its own; nothing forces the
team to do the whole thing in one PR.

### Step 0 — adopt the doc

Everyone reads `ARCHITECTURE.md` + this file. Disagreements get resolved
**before** any code moves. (Not optional. The biggest risk in clean‑arch
refactors is "we agreed in principle but actually disagreed about Finding".)

### Step 1 — extract pure domain types (low risk)

- Add `backend/domain/entities/{scan,finding,endpoint}.py` as `@dataclass`.
- Add converters: `Scan.from_dict(stats_db_manager_record)` and
  `Scan.to_dict(...)` so existing dict‑shaped consumers keep working.
- No imports change in `agents/`, `api/`, or `core/`.

### Step 2 — extract policies (low risk)

- Move `ScopePolicy` (already pure) into
  `backend/domain/value_objects/scope_policy.py` as a re‑export. Old
  imports keep working through a shim.
- Lift the GuardLayer ≥2‑signal rule into
  `backend/domain/policies/evidence_threshold.py` and call it from the
  orchestrator's `event_listener`.

### Step 3 — introduce ports (medium risk)

- Define `ScanRepository`, `FindingRepository`, `EventBusPort`,
  `SocketBroadcaster`, `TerminalEnginePort` as `Protocol`s in
  `backend/domain/ports/`.
- Adapt the existing singletons by adding type hints — no behaviour
  change.

### Step 4 — extract `EnrichFinding` (medium risk)

The cleanest pilot: take the CVSS + Bayesian fusion block out of
`event_listener` and put it in
`backend/use_cases/enrich_finding.py`. The orchestrator becomes:

```python
finding = EnrichFinding(finding_repo, guard, cvss).execute(raw_payload)
if finding is None:
    return  # dropped by guard
await bus.publish(HiveEvent.vuln_confirmed(finding))
await broadcaster.broadcast(VulnUpdateFrame.from_finding(finding))
```

This is the smallest PR that *demonstrates the value*: testable in
isolation, no asyncio, no FastAPI.

### Step 5 — extract `CreateScan` (medium risk)

Move `create_scan` body into `backend/use_cases/create_scan.py`. The
controller becomes a 6‑line FastAPI handler. Tests for "POST /api/scans
returns 202 and persists the scan" become use‑case tests, not API tests.

### Step 6 — split the orchestrator (high risk)

The `bootstrap_hive` function is the hardest target. The plan:

1. Carve out `RunReconUseCase` — owns the recon‑phase wait loop and the
   180 s upper bound.
2. Carve out `RunAssessmentUseCase` — owns the module dispatch loop.
3. Carve out `FinalizeScanUseCase` — owns the
   "promote pending findings → render PDF → emit REPORT_READY" path.
4. The orchestrator becomes:

```python
class ScanLifecycle:
    async def execute(self, scan: Scan) -> None:
        await self.plan(scan)
        await self.recon(scan)
        await self.assessment(scan)
        await self.finalize(scan)
```

This step needs to keep the `event_listener` wiring intact, because
agents subscribe to it. The simplest path is to extract the listener
into `interface_adapters/event_bus/master_listener.py` first, then move
the lifecycle phases.

### Step 7 — split persistence drivers (low risk, last)

`backend/core/scan_state_db.py` and `backend/core/database.py` move under
`frameworks_drivers/persistence/`. The concrete singletons keep their
identity; only the import path changes. This is mostly a `git mv`.

### Step 8 — composition root (final cleanup)

Replace `backend/main.py` with a thin `apps/api_app.py` that imports
adapters and wires use cases. The lifespan keeps doing exactly what it
does today; the difference is that the wiring is explicit instead of
implicit.

---

## 8. What does this NOT do?

- **No agent rename.** Alpha/Beta/Gamma stay where they are; they just gain
  use‑case dependencies in their constructors.
- **No event vocabulary change.** `EventType` is unchanged; it just lives
  in `domain/entities/event.py`.
- **No DB schema change.** Both SQLite and Supabase tables are untouched.
- **No frontend change.** `src/` is not affected.
- **No deletion.** The migration is purely *additive* until step 8, and
  step 8 only relocates existing files.

---

## 9. Acceptance criteria for the migration

A migration step is considered done when:

- [ ] All existing tests pass with no test code modification.
- [ ] No existing import path under `backend/agents/`, `backend/api/`, or
      `backend/core/` was broken.
- [ ] At least one new test exercises the extracted code without booting
      the FastAPI app.
- [ ] The new code has no transitive import of `fastapi`, `aiohttp`,
      `redis`, `supabase`, or `playwright` from inside `domain/`.

---

## 10. Open questions

- **Should agents become use‑case clients or stay event‑driven?** The
  proposed wiring in §6 keeps the EventBus as the integration medium for
  agents, with use‑cases being called from the master `event_listener`.
  An alternative is to make agents "dumb actuators" that wrap a use case
  per event type. The latter is purer but breaks the pub/sub topology.
- **Where do `JobPacket` and `ResultPacket` live?** Today
  `backend/core/protocol.py`. They straddle domain (job semantics) and
  adapter (worker substrate). Defaulting to `domain/entities/` for now.
- **CortexEngine.test_mode** — currently a global flag on the cortex
  singleton (`backend/core/orchestrator.py:127`). In the target it would
  become a parameter on the `LLMPort` factory. That requires a small
  change to the test harness; flag for follow‑up.
- **`stats.json` vs `scan_state.db`** — long term we want a single
  `ScanRepository` backed only by `scan_state.db` and a derived stats
  view. The migration above keeps them side by side.
