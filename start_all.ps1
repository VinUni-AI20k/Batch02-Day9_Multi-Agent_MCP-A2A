$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Error "Python virtual environment not found at $python"
    exit 1
}

$services = @(
    @{ Name = "Registry"; Module = "registry"; Delay = 2 },
    @{ Name = "Tax Agent"; Module = "tax_agent"; Delay = 0 },
    @{ Name = "Compliance Agent"; Module = "compliance_agent"; Delay = 3 },
    @{ Name = "Law Agent"; Module = "law_agent"; Delay = 3 },
    @{ Name = "Customer Agent"; Module = "customer_agent"; Delay = 0 }
)

Write-Host "Starting Stage 5 services in separate PowerShell windows..."

foreach ($service in $services) {
    $command = "Set-Location '$root'; & '$python' -m $($service.Module)"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $command -WorkingDirectory $root
    Write-Host ("Started {0}" -f $service.Name)
    if ($service.Delay -gt 0) {
        Start-Sleep -Seconds $service.Delay
    }
}

Write-Host ""
Write-Host "All service windows were launched."
Write-Host "Test the system from this terminal with:"
Write-Host "  .\.venv\Scripts\python.exe test_client.py"
