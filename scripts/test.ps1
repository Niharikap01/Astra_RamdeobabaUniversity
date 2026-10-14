# Run backend test suite with coverage
$ErrorActionPreference = "Stop"
Write-Host "Running NightWatch backend test suite with coverage..."
pytest backend/tests -v --cov=backend/app --cov-report=term-missing
