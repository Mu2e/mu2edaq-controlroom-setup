<#
.SYNOPSIS
    Tear down the control room from this Windows machine (PowerShell port of
    bin/stop-controlroom.sh): close all tunnels, then stop all VNC sessions.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$CrsRemote = Join-Path $Root 'venv\Scripts\crs-remote.exe'
$CrsTunnel = Join-Path $Root 'venv\Scripts\crs-tunnel.exe'
if (-not (Test-Path $CrsRemote)) {
    Write-Error 'Run .\bootstrap.ps1 first to create the venv.'
    exit 1
}

# Closing tunnels is best-effort; still stop the sessions if it fails.
try { & $CrsTunnel close --all } catch { }
& $CrsRemote stop --all

Write-Host ''
Write-Host 'Control room is down.'
