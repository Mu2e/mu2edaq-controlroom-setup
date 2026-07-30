<#
.SYNOPSIS
    Bootstrap mu2edaq-controlroom-setup on Windows (PowerShell port of
    bootstrap.sh): create venv, install the package with GUI support plus the
    sibling mu2edaq-discovery package.

.DESCRIPTION
    The server-side VNC scripts under server/ run on the Linux DAQ cluster and
    are not ported. SSH tunnel multiplexing (ControlMaster) is limited on
    Windows OpenSSH -- see WINDOWS-COMPATIBILITY-REPORT.md and Mu2e/mu2edaq-main#12.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Here

# Prefer 'python'; fall back to the py launcher ('python3' on Windows is the
# Microsoft Store alias stub, so it is not used here).
$Python = $env:PYTHON
if (-not $Python) {
    if (Get-Command python -ErrorAction SilentlyContinue) { $Python = 'python' }
    elseif (Get-Command py -ErrorAction SilentlyContinue) { $Python = 'py' }
    else { Write-Error 'Python 3.9+ not found on PATH. Install it first.'; exit 1 }
}

if (-not (Test-Path 'venv')) {
    & $Python -m venv venv
}
$VenvPy = Join-Path $Here 'venv\Scripts\python.exe'
& $VenvPy -m pip install --upgrade pip | Out-Null

# Prefer the sibling submodule checkout of mu2edaq-discovery when present.
if (Test-Path '..\mu2edaq-discovery') {
    & $VenvPy -m pip install -e '..\mu2edaq-discovery'
}
& $VenvPy -m pip install -e '.[gui,dev]'

Write-Host 'Done. Entry points in venv\Scripts: crs-tunnel crs-remote crs-gui'
Write-Host 'Run tests with: venv\Scripts\pytest.exe'
