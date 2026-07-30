<#
.SYNOPSIS
    Bring up the full control room from this (external) Windows machine
    (PowerShell port of bin/start-controlroom.sh): start all VNC sessions on
    the cluster, then open all tunnels.
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

& $CrsRemote start --all
& $CrsTunnel open --all

Write-Host ''
Write-Host 'Control room is up. Attach with: venv\Scripts\crs-tunnel connect --session <name>'
Write-Host 'Or launch the GUI:               venv\Scripts\crs-gui'
