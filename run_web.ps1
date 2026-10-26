$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir
$env:PYTHONPATH = "src"
& ".\.venv\Scripts\python.exe" -m uvicorn cadpatch.web.app:app --host 127.0.0.1 --port 8000
