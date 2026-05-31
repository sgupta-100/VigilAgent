<#
.SYNOPSIS
    Delete clearly-dead scratch files from the repo root (debug scripts and harness logs).

.DESCRIPTION
    Fail-closed safety: any file modified within the last 24 hours is automatically
    skipped, even if -Confirm:$false is passed. Dry-run is the default; deletion only
    happens with explicit -Confirm:$false.

    Always start with:
        powershell -NoProfile -File scripts\cleanup_delete.ps1 -WhatIf

    Then, after reviewing the list:
        powershell -NoProfile -File scripts\cleanup_delete.ps1 -Confirm:$false

.NOTES
    Companion: scripts/cleanup_archive.ps1 (handles .md archival).
    Source of truth: docs/CLEANUP_PLAN.md
#>

[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param()

$ErrorActionPreference = 'Stop'

# Resolve repo root from this script's location: scripts/ -> repo root
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath $RepoRoot)) {
    throw "Repo root not found: $RepoRoot"
}

# Files to delete — sourced from docs/CLEANUP_PLAN.md
$DeleteTargets = @(
    '_tmp_full_op.py',
    '_check_ffuf.py',
    '_test_infra.py',
    '_test_recon_full.py',
    '_test_stdin_tool.py',
    '_harness_run1.log',
    '_harness_run2.log',
    '_harness_run3.log',
    '_harness_run4.log',
    'tmp_browser_smoke.py'
)

$RecencyThreshold = (Get-Date).AddHours(-24)

$deleted = 0
$skippedRecent = 0
$skippedMissing = 0

foreach ($name in $DeleteTargets) {
    $path = Join-Path $RepoRoot $name

    if (-not (Test-Path -LiteralPath $path)) {
        Write-Host "[skip] $name - already gone" -ForegroundColor DarkGray
        $skippedMissing++
        continue
    }

    $item = Get-Item -LiteralPath $path
    if ($item.LastWriteTime -gt $RecencyThreshold) {
        Write-Warning "[skip-recent] $name was modified $($item.LastWriteTime) (<24h); refusing to delete"
        $skippedRecent++
        continue
    }

    if ($PSCmdlet.ShouldProcess($path, 'Remove-Item')) {
        Remove-Item -LiteralPath $path -Force -ErrorAction Stop
        Write-Host "[deleted] $name" -ForegroundColor Yellow
        $deleted++
    }
}

Write-Host ''
Write-Host "Summary: deleted=$deleted  skipped-recent=$skippedRecent  skipped-missing=$skippedMissing" -ForegroundColor Cyan
if ($skippedRecent -gt 0) {
    Write-Host "Re-run after the 24h safety window expires for files still on disk." -ForegroundColor DarkYellow
}
