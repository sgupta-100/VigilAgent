<#
.SYNOPSIS
    Archive (move) progress-log .md files from the repo root into .archive/progress-logs/.

.DESCRIPTION
    Reversible by design: files are MOVED, never deleted. Re-running is idempotent —
    files already moved are reported and skipped. The destination directory is created
    on demand. The script never touches files outside its hardcoded list, so accidentally
    invoking it with extra arguments cannot widen its blast radius.

.NOTES
    Companion: scripts/cleanup_delete.ps1 (handles scratch py/log removals).
    Source of truth: docs/CLEANUP_PLAN.md
#>

[CmdletBinding(SupportsShouldProcess = $true)]
param()

$ErrorActionPreference = 'Stop'

# Resolve repo root from this script's location: scripts/ -> repo root
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath $RepoRoot)) {
    throw "Repo root not found: $RepoRoot"
}

$ArchiveDir = Join-Path $RepoRoot '.archive\progress-logs'
if (-not (Test-Path -LiteralPath $ArchiveDir)) {
    if ($PSCmdlet.ShouldProcess($ArchiveDir, 'Create archive directory')) {
        New-Item -ItemType Directory -Path $ArchiveDir -Force | Out-Null
        Write-Host "Created archive directory: $ArchiveDir" -ForegroundColor Cyan
    }
}

# Files to archive — sourced from docs/CLEANUP_PLAN.md
$ArchiveTargets = @(
    'CI_CD_FIXES_COMPLETE.md',
    'CODE_ORGANIZATION_ASSESSMENT.md',
    'COMPREHENSIVE_FIX_PLAN.md',
    'FINAL_PUSH_SUMMARY.md',
    'FIXES_APPLIED_MAY_26_2026.md',
    'GITHUB_UPLOAD_COMPLETE.md',
    'LIFECYCLE_ANALYSIS_AND_FIXES.md',
    'MODEL_SWITCH_SUMMARY.md',
    'PUSH_SUCCESS_SUMMARY.md',
    'REMAINING_WORK_ANALYSIS.md',
    'REMAINING_WORK_PLAN.md',
    'REPOSITORY_ORGANIZATION.md',
    'STATUS.md',
    'TEST_COVERAGE_UPDATE.md',
    'TEST_FIXES_COMPLETE_MAY_25.md',
    'TEST_FIXES_COMPLETE_MAY_26_2026.md',
    'TEST_INFRASTRUCTURE_SETUP.md',
    'TESTING_IMPLEMENTATION_PHASE1.md',
    'UPLOAD_COMPLETE_MAY_26_2026.md',
    'WIPE_HISTORY_FIX.md'
)

$moved = 0
$missing = 0
$collision = 0

foreach ($name in $ArchiveTargets) {
    $src = Join-Path $RepoRoot $name
    $dst = Join-Path $ArchiveDir $name

    if (-not (Test-Path -LiteralPath $src)) {
        Write-Host "[skip] $name - already archived or missing" -ForegroundColor DarkGray
        $missing++
        continue
    }

    if (Test-Path -LiteralPath $dst) {
        Write-Warning "[collision] $name already exists in archive; leaving source untouched"
        $collision++
        continue
    }

    if ($PSCmdlet.ShouldProcess($src, "Move to $dst")) {
        Move-Item -LiteralPath $src -Destination $dst -ErrorAction Stop
        Write-Host "[moved] $name -> .archive/progress-logs/" -ForegroundColor Green
        $moved++
    }
}

Write-Host ''
Write-Host "Summary: moved=$moved  skipped=$missing  collisions=$collision" -ForegroundColor Cyan
Write-Host "Archive root: $ArchiveDir"
