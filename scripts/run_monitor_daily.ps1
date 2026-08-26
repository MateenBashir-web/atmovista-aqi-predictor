# Run daily forecast-vs-actual monitoring (local Windows task / manual)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if (Test-Path .\.venv\Scripts\Activate.ps1) {
    . .\.venv\Scripts\Activate.ps1
}

$env:STORAGE_MODE = if ($env:STORAGE_MODE) { $env:STORAGE_MODE } else { "local" }
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"

Write-Host "[monitor-daily] Running forecast vs actual pipeline..."
python -u pipelines\monitor_pipeline.py

Write-Host "[monitor-daily] Refreshing report artifacts..."
python -u pipelines\generate_report_artifacts.py --cities-only

Write-Host "[monitor-daily] Done."
