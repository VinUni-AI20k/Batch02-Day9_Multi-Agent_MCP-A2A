# start_all.ps1
# Start all Legal Multi-Agent System services on Windows

$PythonPath = ".\.venv\Scripts\python.exe"
$Wd = (Get-Location).Path

Write-Host "Starting Registry service on port 10000..."
Start-Process -FilePath $PythonPath -ArgumentList "-m registry" -WorkingDirectory $Wd
Start-Sleep -Seconds 2

Write-Host "Starting Tax Agent on port 10102..."
Start-Process -FilePath $PythonPath -ArgumentList "-m tax_agent" -WorkingDirectory $Wd
Start-Sleep -Seconds 1

Write-Host "Starting Compliance Agent on port 10103..."
Start-Process -FilePath $PythonPath -ArgumentList "-m compliance_agent" -WorkingDirectory $Wd
Start-Sleep -Seconds 3

Write-Host "Starting Law Agent on port 10101..."
Start-Process -FilePath $PythonPath -ArgumentList "-m law_agent" -WorkingDirectory $Wd
Start-Sleep -Seconds 3

Write-Host "Starting Customer Agent on port 10100..."
Start-Process -FilePath $PythonPath -ArgumentList "-m customer_agent" -WorkingDirectory $Wd

Write-Host ""
Write-Host "========================================="
Write-Host "All services started in separate windows:"
Write-Host "  Registry:         http://localhost:10000"
Write-Host "  Customer Agent:   http://localhost:10100"
Write-Host "  Law Agent:        http://localhost:10101"
Write-Host "  Tax Agent:        http://localhost:10102"
Write-Host "  Compliance Agent: http://localhost:10103"
Write-Host "========================================="
Write-Host ""
Write-Host "Run test_client.py to send a query:"
Write-Host "  uv run python test_client.py"
Write-Host ""
