$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location -LiteralPath $ProjectRoot

$python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Virtual environment not found. Run: python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.in"
}

$env:PYTHONPATH = Join-Path $ProjectRoot "src"
& $python -m streamlit run (Join-Path $ProjectRoot "app.py")
