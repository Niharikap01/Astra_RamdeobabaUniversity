# Start FastAPI backend server on port 8000
$ErrorActionPreference = "Stop"
Write-Host "Starting NightWatch backend on http://0.0.0.0:8000..."
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
