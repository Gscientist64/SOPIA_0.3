<#
.SYNOPSIS
    Installs the SOPIA API as a Windows service using NSSM.

.DESCRIPTION
    For a Windows VM deployment. Runs `backend\serve.py` under the project's
    virtualenv, restarts it on failure, and rotates logs into backend\logs.

    Requires NSSM (https://nssm.cc) on PATH, or pass -NssmPath.
    Run from an elevated (Administrator) PowerShell prompt.

.EXAMPLE
    .\install-sopia-service.ps1 -ProjectRoot C:\sopia -ServiceName sopia-api
#>
[CmdletBinding()]
param(
    [string]$ProjectRoot,
    [string]$ServiceName = 'sopia-api',
    [string]$NssmPath = 'nssm',
    [int]$Port = 8000,
    [int]$Workers = 2
)

$ErrorActionPreference = 'Stop'

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
}

if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
        ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script from an elevated (Administrator) PowerShell prompt.'
}

$backend = Join-Path $ProjectRoot 'backend'
$python  = Join-Path $backend 'venv\Scripts\python.exe'
$serve   = Join-Path $backend 'serve.py'
$envFile = Join-Path $ProjectRoot '.env'
$logDir  = Join-Path $backend 'logs'

foreach ($required in @($python, $serve, $envFile)) {
    if (-not (Test-Path $required)) { throw "Required file not found: $required" }
}
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    Write-Host "Service '$ServiceName' already exists - reconfiguring."
    & $NssmPath stop $ServiceName | Out-Null
} else {
    & $NssmPath install $ServiceName $python | Out-Null
}

# serve.py changes into its own directory, so migrations and uploads resolve
# relative to the backend folder.
& $NssmPath set $ServiceName AppParameters "`"$serve`" --host 0.0.0.0 --port $Port --workers $Workers"
& $NssmPath set $ServiceName AppDirectory $backend
& $NssmPath set $ServiceName DisplayName 'SOPIA API'
& $NssmPath set $ServiceName Description 'Standard Operating Procedure Intelligent Assistant'
& $NssmPath set $ServiceName Start SERVICE_AUTO_START
& $NssmPath set $ServiceName AppStdout (Join-Path $logDir 'sopia-api.out.log')
& $NssmPath set $ServiceName AppStderr (Join-Path $logDir 'sopia-api.err.log')
& $NssmPath set $ServiceName AppRotateFiles 1
& $NssmPath set $ServiceName AppRotateBytes 10485760
& $NssmPath set $ServiceName AppExit Default Restart
& $NssmPath set $ServiceName AppRestartDelay 5000

& $NssmPath start $ServiceName | Out-Null
Start-Sleep -Seconds 3
Get-Service -Name $ServiceName | Format-List Name, Status, StartType
Write-Host ''
Write-Host "Logs      : $logDir"
Write-Host "Health    : http://localhost:$Port/health"
Write-Host "Readiness : http://localhost:$Port/ready"
