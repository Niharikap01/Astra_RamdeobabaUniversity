# Start React + Vite dashboard on port 5173
$ErrorActionPreference = "Stop"
Write-Host "Starting NightWatch dashboard on http://localhost:5173..."
Set-Location "$PSScriptRoot\..\dashboard"
npm run dev
