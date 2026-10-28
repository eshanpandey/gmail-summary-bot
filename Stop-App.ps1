param(
    [switch]$StopAllOllama
)

$ErrorActionPreference = 'Continue'
$stateDir = Join-Path $PSScriptRoot '.runtime'

function Stop-RecordedProcess([string]$name) {
    $pidFile = Join-Path $stateDir "$name.pid"
    if (-not (Test-Path $pidFile)) { return }
    $processId = Get-Content $pidFile -Raw
    Stop-Process -Id $processId.Trim() -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    Write-Host "Stopped $name process."
}

# Stop the project Flask process first. Ollama is stopped only if Start-App.ps1 launched it.
Stop-RecordedProcess 'app'
Stop-RecordedProcess 'ollama'
if ($StopAllOllama) {
    Get-Process -Name 'ollama','ollama app' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host 'Stopped all local Ollama processes.'
}
if (Test-Path $stateDir) { Remove-Item -LiteralPath $stateDir -Force -ErrorAction SilentlyContinue }
