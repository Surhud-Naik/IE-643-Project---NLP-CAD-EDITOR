@echo off
setlocal
cd /d "%~dp0"
set PYTHONPATH=src
.\.venv\Scripts\python.exe -m uvicorn cadpatch.web.app:app --host 127.0.0.1 --port 8000
