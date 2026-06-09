$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$uiPort = if ($env:DEMO_UI_PORT) { $env:DEMO_UI_PORT } else { "8008" }

if (-not (Test-Path $python)) {
    Write-Error "Python virtual environment not found at $python"
    exit 1
}

Write-Host "Starting full Stage 5 stack in a background PowerShell window..."
$command = "Set-Location '$root'; & '$python' 'run_full_stack.py'"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $command -WorkingDirectory $root

Start-Sleep -Seconds 4
Start-Process "http://localhost:$uiPort"

Write-Host ""
Write-Host "Browser opened at http://localhost:$uiPort"
Write-Host "Logs are written to .stage5_logs\\"
