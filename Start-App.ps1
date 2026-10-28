$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$stateDir = Join-Path $projectRoot '.runtime'
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

function Test-OllamaRunning {
    try {
        Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://127.0.0.1:11434/api/tags' | Out-Null
        return $true
    } catch { return $false }
}

if (-not (Test-OllamaRunning)) {
    $ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
    $ollamaExecutable = if ($ollamaCommand) { $ollamaCommand.Source } else { Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe' }
    if (-not (Test-Path $ollamaExecutable)) { throw 'Ollama is not installed or could not be located.' }
    $ollamaProcess = Start-Process -FilePath $ollamaExecutable -ArgumentList 'serve' -PassThru -WindowStyle Hidden
    $ollamaProcess.Id | Set-Content (Join-Path $stateDir 'ollama.pid')
    Start-Sleep -Seconds 2
}

$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw 'Virtual environment missing. Create .venv and install requirements before starting the app.'
}

$appProcess = Start-Process -FilePath $python -ArgumentList 'app.py' -WorkingDirectory $projectRoot -PassThru -WindowStyle Hidden
$appProcess.Id | Set-Content (Join-Path $stateDir 'app.pid')
Write-Host 'Inbox Brief started at http://localhost:5000'
Write-Host 'Run .\Stop-App.ps1 when you are done.'
