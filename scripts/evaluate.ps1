$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv_check\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Evaluation interpreter not found: $python"
}

Push-Location $repoRoot
try {
    & $python -m ml.robustness
    if ($LASTEXITCODE -ne 0) {
        throw "Evaluation failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
