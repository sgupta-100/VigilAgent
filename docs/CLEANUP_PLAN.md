# Repository Cleanup Plan

**Generated:** 2026-05-31
**Scope:** Repo root only. No code under `backend/`, `src/`, `tests/`, `.kiro/`, `.agents/`, `config/`, `scripts/`, `tools/`, `docker/` is touched.
**Mode:** Proposal only. Nothing is moved or deleted by this document. Use `scripts/cleanup_archive.ps1` and `scripts/cleanup_delete.ps1` for actions, both gated.

## Verification methodology

For every candidate at the repo root the filename was grepped against:

- `backend/**`
- `src/**`
- `tests/**`
- `docs/**`
- `config/**`
- `scripts/**`
- `tools/**`
- `docker/**`
- `.github/**` (workflows + actions)
- root config files (`.gitignore`, `.gitattributes`, `package.json`, `pytest.ini`, `sonar-project.properties`, `vite.config.js`, `.eslintrc.cjs`, `Dockerfile*`, `docker-compose.yml`, `nginx.conf`, `requirements.txt`, `skills-lock.json`)

A file is marked **DELETE-SAFE** or **ARCHIVE-SAFE** only when zero matches were returned across all the above scopes.

## Markdown files at repo root — disposition

| File | Size | Disposition | Proof |
|---|---:|---|---|
| `README.md` | 6.7 KB | **KEEP** | Standard repo entry point. |
| `LICENSE` | 1.1 KB | **KEEP** | Required. |
| `CONTRIBUTING.md` | 13.9 KB | **KEEP** | Standard, referenced by GitHub UI. |
| `CI_CD_FIXES_COMPLETE.md` | 9.0 KB | **ARCHIVE** | No references in `backend/`, `src/`, `tests/`, `docs/`, `config/`, `scripts/`, `tools/`, `docker/`, `.github/workflows/`. Progress log. |
| `CODE_ORGANIZATION_ASSESSMENT.md` | 12.4 KB | **ARCHIVE** | Same proof. Snapshot assessment, superseded. |
| `COMPREHENSIVE_FIX_PLAN.md` | 3.7 KB | **ARCHIVE** | Same proof. Draft plan. |
| `FINAL_PUSH_SUMMARY.md` | 8.1 KB | **ARCHIVE** | Same proof. Push log. |
| `FIXES_APPLIED_MAY_26_2026.md` | 6.0 KB | **ARCHIVE** | Same proof. Daily fix log. |
| `GITHUB_UPLOAD_COMPLETE.md` | 11.4 KB | **ARCHIVE** | Same proof. Upload log. |
| `LIFECYCLE_ANALYSIS_AND_FIXES.md` | 11.5 KB | **ARCHIVE** | Same proof. Analysis snapshot. |
| `MODEL_SWITCH_SUMMARY.md` | 3.9 KB | **ARCHIVE** | Same proof. One-off summary. |
| `PUSH_SUCCESS_SUMMARY.md` | 5.7 KB | **ARCHIVE** | Same proof. Push log. |
| `REMAINING_WORK_ANALYSIS.md` | 7.3 KB | **ARCHIVE** | Same proof. Snapshot. |
| `REMAINING_WORK_PLAN.md` | 2.3 KB | **ARCHIVE** | Same proof. Plan draft. |
| `REPOSITORY_ORGANIZATION.md` | 9.6 KB | **ARCHIVE** | Same proof. Reorg notes; superseded by `docs/PROJECT_REORGANIZATION_SUMMARY.md`. |
| `STATUS.md` | 4.3 KB | **ARCHIVE** | Same proof. Note: `docs/PROJECT_REORGANIZATION_SUMMARY.md` mentions a `STATUS.md` but at `.kiro/specs/openclaw-integration/STATUS.md`, not the root file. |
| `TEST_COVERAGE_UPDATE.md` | 6.0 KB | **ARCHIVE** | Same proof. |
| `TEST_FIXES_COMPLETE_MAY_25.md` | 7.4 KB | **ARCHIVE** | Same proof. |
| `TEST_FIXES_COMPLETE_MAY_26_2026.md` | 9.5 KB | **ARCHIVE** | Same proof. |
| `TEST_INFRASTRUCTURE_SETUP.md` | 11.9 KB | **ARCHIVE** | Same proof. |
| `TESTING_IMPLEMENTATION_PHASE1.md` | 9.2 KB | **ARCHIVE** | Same proof. |
| `UPLOAD_COMPLETE_MAY_26_2026.md` | 5.3 KB | **ARCHIVE** | Same proof. |
| `WIPE_HISTORY_FIX.md` | 8.1 KB | **ARCHIVE** | Same proof. Git history maintenance log. |

ARCHIVE preserves history (move under `.archive/progress-logs/<original-name>`) without polluting the root. The existing `.archive/` already has `session-reports/` and `status-updates/` subfolders, so the convention is in place.

## Other root-level scratch files — disposition

| File | Size | Disposition | Proof |
|---|---:|---|---|
| `_tmp_full_op.py` | 20.0 KB | **DELETE** | Filename is unreferenced anywhere; underscore-prefix convention indicates a one-shot scratch script. |
| `_check_ffuf.py` | 149 B | **DELETE** | Same proof. 4-line debug snippet. |
| `_test_infra.py` | 14.0 KB | **DELETE** | Same proof. Underscore-prefixed; not collected by `pytest.ini` (which targets `tests/`). |
| `_test_recon_full.py` | 5.9 KB | **DELETE** | Same proof. |
| `_test_stdin_tool.py` | 1.7 KB | **DELETE** | Same proof. |
| `_harness_run1.log` | 5.4 KB | **DELETE** | Run log. Zero references. |
| `_harness_run2.log` | 5.4 KB | **DELETE** | Same. |
| `_harness_run3.log` | 8.4 KB | **DELETE** | Same. |
| `_harness_run4.log` | 8.4 KB | **DELETE** | Same. |
| `tmp_browser_smoke.py` | 2.0 KB | **DELETE** | Filename `tmp_*` and zero references. |

`scripts/cleanup_delete.ps1` will refuse to delete any file modified within the last 24 hours (fail-closed). Several of the `_harness_run*.log` and `_test_*.py` files were last modified 2026-05-31; if you run the script today they will be skipped and the user has to consciously decide.

## Files explicitly NOT touched (per directive)

| Path | Why kept |
|---|---|
| `stats.json` (17 MB) | Runtime state per directive. |
| `keyring.json` | Runtime data per directive. |
| `user_config.json` | Runtime data per directive. |
| `.env`, `.env.example` | Configuration. |
| `package.json`, `package-lock.json` | Lock files per directive. |
| `pytest.ini`, `vite.config.js`, `tailwind.config.js`, `postcss.config.js`, `.eslintrc.cjs` | Active configs. |
| `Dockerfile`, `Dockerfile.frontend`, `docker-compose.yml`, `nginx.conf` | Build/deploy. |
| `index.html` | Vite entry. |
| `requirements.txt`, `sonar-project.properties`, `skills-lock.json` | Active configs. |
| `dist/` | Build artifact, gitignored. |
| `node_modules/` | Dependencies. |
| `graphify-out/` | Output of `scripts/graphify_scan.py` (verified — line 268). |
| `local_node/` | Referenced by `scripts/start_vulagent.py` (verified — line 43). |
| `__pycache__/`, `.pytest_cache/` | Python caches, gitignored. |

## Reorganization proposals (NOT executed — human review required)

These look misplaced. They are listed only; no script moves them.

| Current path | Proposed target | Reason |
|---|---|---|
| `docs/cleanup_assessment_7_tracks.md` | `docs/archive/cleanup_assessment_7_tracks.md` | Lowercase + outdated assessment; `docs/archive/` already exists for retired docs. |
| `docs/exhaustive_audit.md` | `docs/archive/exhaustive_audit.md` | Same pattern. |
| `docs/FIX_PROGRESS.md` | `docs/archive/FIX_PROGRESS.md` | Progress log style; matches archive policy. |
| `docs/AUDIT_UPDATE_2026_05_24.md` | `docs/archive/AUDIT_UPDATE_2026_05_24.md` | Dated audit, superseded. |
| `brain_test_infra/` | `tests/brain_infra/` | If only used by tests. Needs human verification of imports first. |
| `testsprite_tests/` | `tests/testsprite/` | Same. |

If any of these moves break imports, the rename must update the importers. That's why they are proposals, not script actions.

# Repo Layout

Desired top-level layout after cleanup (top-level dirs only):

```
penetration testing system/
├── .agents/              # Skill packs (read-only library)
├── .archive/             # Retired docs and progress logs (this PR adds progress-logs/)
├── .github/              # Workflows + GitHub config
├── .kiro/                # Kiro specs and steering
├── .node/                # Bundled Node runtime
├── .planning/            # Active planning docs
├── .vscode/              # Editor config
├── backend/              # Python backend (agents, core, api)
├── brain/                # Brain runtime
├── brain_test_infra/     # Brain test scaffolding (move proposal pending)
├── config/               # YAML / TOML configs
├── data/                 # Runtime data
├── dist/                 # Build artifacts (gitignored)
├── docker/               # Docker compose stacks
├── docs/                 # Documentation
│   └── archive/          # Retired docs
├── extension/            # Browser extension (Chrome MV3)
├── graphify-out/         # graphify_scan.py output
├── legacy/               # Empty / archive
├── local_node/           # Bundled portable Node (used by start_vulagent.py)
├── logs/                 # Runtime logs
├── node_modules/         # NPM deps (gitignored)
├── reports/              # Generated PDF / HTML reports
├── scan_states/          # Persistent scan state
├── scripts/              # Operator scripts
├── src/                  # Frontend (Vite + React)
├── static/               # Static assets
├── tests/                # Pytest suite
├── testsprite_tests/     # Sprite-based tests (move proposal pending)
└── tools/                # Tool integrations
```

Root files retained:
`.env`, `.env.example`, `.eslintrc.cjs`, `.gitattributes`, `.gitignore`, `CONTRIBUTING.md`,
`docker-compose.yml`, `Dockerfile`, `Dockerfile.frontend`, `index.html`, `keyring.json`,
`LICENSE`, `nginx.conf`, `package-lock.json`, `package.json`, `postcss.config.js`,
`pytest.ini`, `README.md`, `requirements.txt`, `skills-lock.json`,
`sonar-project.properties`, `stats.json`, `tailwind.config.js`, `user_config.json`,
`vite.config.js`.

Result: 19 progress-log .md files leave the root, 10 scratch py/log files leave the root, root signal-to-noise dramatically improves.

## Execution

```powershell
# Step 1 — review this document
# Step 2 — archive (always reversible, keeps file under .archive/progress-logs/)
powershell -NoProfile -File scripts\cleanup_archive.ps1

# Step 3 — preview deletes (dry-run; files modified <24h are skipped automatically)
powershell -NoProfile -File scripts\cleanup_delete.ps1 -WhatIf

# Step 4 — actually delete (only after reviewing the -WhatIf output)
powershell -NoProfile -File scripts\cleanup_delete.ps1 -Confirm:$false
```
