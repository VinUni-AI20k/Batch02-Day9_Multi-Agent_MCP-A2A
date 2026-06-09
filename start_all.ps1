# start_all.ps1 — Start all Legal Multi-Agent System services on Windows
# Usage: .\start_all.ps1
# Requires: uv (or activate venv first)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

# Detect python: prefer uv run, fallback to venv
$uvCmd = Get-Command uv -ErrorAction SilentlyContinue
if ($uvCmd) {
    $launcher = { param($m) Start-Process "uv" -ArgumentList "run","python","-m",$m -WorkingDirectory $root -WindowStyle Normal }
} else {
    $pyExe = if (Test-Path "$root\.venv\Scripts\python.exe") { "$root\.venv\Scripts\python.exe" } else { "python" }
    $launcher = { param($m) Start-Process $pyExe -ArgumentList "-m",$m -WorkingDirectory $root -WindowStyle Normal }
}

Write-Host "Starting Legal Multi-Agent System..."
Write-Host ""

# 1. Registry (must be first)
& $launcher "registry"
Write-Host "[1/5] Registry        http://localhost:10000"
Start-Sleep -Seconds 3

# 2. Leaf agents (Tax + Compliance, no inter-agent deps)
& $launcher "tax_agent"
Write-Host "[2/5] Tax Agent       http://localhost:10102"
& $launcher "compliance_agent"
Write-Host "[3/5] Compliance      http://localhost:10103"
Start-Sleep -Seconds 4

# 3. Law Agent (orchestrates tax + compliance)
& $launcher "law_agent"
Write-Host "[4/5] Law Agent       http://localhost:10101"
Start-Sleep -Seconds 4

# 4. Customer Agent (entry point)
& $launcher "customer_agent"
Write-Host "[5/5] Customer Agent  http://localhost:10100"

Write-Host ""
Write-Host "Waiting 10s for agents to register with Registry..."
Start-Sleep -Seconds 10

# Verify
Write-Host ""
Write-Host "=== Service Status ==="
$services = @(
    @{port=10000; name="Registry       "},
    @{port=10100; name="Customer Agent "},
    @{port=10101; name="Law Agent      "},
    @{port=10102; name="Tax Agent      "},
    @{port=10103; name="Compliance     "}
)
foreach ($s in $services) {
    $conn = Get-NetTCPConnection -LocalPort $s.port -State Listen -ErrorAction SilentlyContinue
    if ($conn) { Write-Host "  OK   $($s.name) port $($s.port)" }
    else        { Write-Host "  FAIL $($s.name) port $($s.port) - not listening" }
}

Write-Host ""
Write-Host "=== Registered Agents ==="
try {
    $reg = Invoke-RestMethod -Uri "http://localhost:10000/agents" -TimeoutSec 5
    foreach ($a in $reg.agents) {
        Write-Host "  $($a.agent_name)  ->  $($a.endpoint)"
    }
} catch {
    Write-Host "  Could not reach registry"
}

Write-Host ""
Write-Host "Run test:  uv run python test_client.py"
