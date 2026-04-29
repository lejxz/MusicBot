<#
Windows installer PowerShell script for Discord Music Bot
Usage (PowerShell):
  .\install.ps1            # create venv and install deps
  .\install.ps1 -Run      # create venv and run bot in foreground
  .\install.ps1 -CreateTask # create a Scheduled Task to run at logon
#>

param(
    [switch]$Run,
    [switch]$CreateTask
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Write-Host "Installing in: $ScriptDir"

# Check python
try {
    $py = Get-Command python -ErrorAction Stop
} catch {
    Write-Error "python not found in PATH. Install Python 3.11+ and ensure it's on PATH."
    exit 1
}

# Create venv
$VenvPath = Join-Path $ScriptDir 'venv'
if (-not (Test-Path $VenvPath)) {
    Write-Host "Creating virtual environment..."
    & python -m venv $VenvPath
}

# Activate and install
$Activate = Join-Path $VenvPath 'Scripts\Activate.ps1'
if (-not (Test-Path $Activate)) {
    Write-Error "Virtualenv activation script not found: $Activate"
    exit 1
}

Write-Host "Activating venv and installing requirements..."
& powershell -NoProfile -ExecutionPolicy Bypass -Command ". '$Activate'; python -m pip install --upgrade pip; if (Test-Path 'requirements.txt') { pip install -r requirements.txt }"

# Copy .env.example if .env missing
$EnvFile = Join-Path $ScriptDir '.env'
$EnvExample = Join-Path $ScriptDir '.env.example'
if (-not (Test-Path $EnvFile) -and (Test-Path $EnvExample)) {
    Copy-Item $EnvExample $EnvFile
    Write-Host "Copied .env.example to .env — please edit .env to add your DISCORD_TOKEN"
}

Write-Host "Install complete. To run:"
Write-Host "  PowerShell: .\venv\Scripts\Activate.ps1; python index.py"

if ($CreateTask) {
    Write-Host "Creating Scheduled Task 'DiscordMusicBot' to run at logon..."
    $TaskName = 'DiscordMusicBot'
    $PythonExe = Join-Path $VenvPath 'Scripts\python.exe'
    $Action = "$PythonExe `"$ScriptDir\index.py`""
    $Schtasks = "schtasks /Create /SC ONLOGON /RL HIGHEST /TN $TaskName /TR `"$Action`" /F"
    Write-Host "Running: $Schtasks"
    Invoke-Expression $Schtasks
    Write-Host "Scheduled task created. Use Task Scheduler to adjust triggers or credentials if necessary."
}

if ($Run) {
    Write-Host "Starting bot in foreground... (Ctrl+C to stop)"
    & powershell -NoProfile -ExecutionPolicy Bypass -Command ". '$Activate'; python index.py"
}
