# Start all Legal Multi-Agent System services on Windows PowerShell, logging output to files
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = 1

$logDir = Join-Path $PSScriptRoot "logs"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

$processes = @()

try {
    Write-Host "Starting Registry service on port 10000..." -ForegroundColor Cyan
    $processes += Start-Process -FilePath "uv" -ArgumentList "run", "python", "-m", "registry" -PassThru -NoNewWindow `
        -RedirectStandardOutput (Join-Path $logDir "registry.log") -RedirectStandardError (Join-Path $logDir "registry_err.log")

    Start-Sleep -Seconds 2

    Write-Host "Starting Tax Agent on port 10102..." -ForegroundColor Cyan
    $processes += Start-Process -FilePath "uv" -ArgumentList "run", "python", "-m", "tax_agent" -PassThru -NoNewWindow `
        -RedirectStandardOutput (Join-Path $logDir "tax.log") -RedirectStandardError (Join-Path $logDir "tax_err.log")

    Write-Host "Starting Compliance Agent on port 10103..." -ForegroundColor Cyan
    $processes += Start-Process -FilePath "uv" -ArgumentList "run", "python", "-m", "compliance_agent" -PassThru -NoNewWindow `
        -RedirectStandardOutput (Join-Path $logDir "compliance.log") -RedirectStandardError (Join-Path $logDir "compliance_err.log")

    Start-Sleep -Seconds 3

    Write-Host "Starting Law Agent on port 10101..." -ForegroundColor Cyan
    $processes += Start-Process -FilePath "uv" -ArgumentList "run", "python", "-m", "law_agent" -PassThru -NoNewWindow `
        -RedirectStandardOutput (Join-Path $logDir "law.log") -RedirectStandardError (Join-Path $logDir "law_err.log")

    Start-Sleep -Seconds 3

    Write-Host "Starting Customer Agent on port 10100..." -ForegroundColor Cyan
    $processes += Start-Process -FilePath "uv" -ArgumentList "run", "python", "-m", "customer_agent" -PassThru -NoNewWindow `
        -RedirectStandardOutput (Join-Path $logDir "customer.log") -RedirectStandardError (Join-Path $logDir "customer_err.log")

    Write-Host ""
    Write-Host "All 5 services launched successfully! Output logs are saved in the 'logs/' folder." -ForegroundColor Green
    Write-Host "  Registry:         http://localhost:10000"
    Write-Host "  Customer Agent:   http://localhost:10100"
    Write-Host "  Law Agent:        http://localhost:10101"
    Write-Host "  Tax Agent:        http://localhost:10102"
    Write-Host "  Compliance Agent: http://localhost:10103"
    Write-Host ""
    Write-Host "Keep this task running to keep the services alive. Terminating this task will stop all services."
    Write-Host ""

    # Infinite loop to keep the process group alive
    while ($true) {
        Start-Sleep -Seconds 5
    }
} finally {
    Write-Host "Stopping all background processes..." -ForegroundColor Yellow
    foreach ($p in $processes) {
        if ($p -and -not $p.HasExited) {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
