@echo off
cd /d "%~dp0"
echo Installing dependencies (first run only)...
uv pip install -e . >nul 2>&1
echo Cleaning temporary files...
if exist "data\output" rmdir /s /q "data\output"
if exist "data\preview_cache" rmdir /s /q "data\preview_cache"
mkdir "data\output" "data\preview_cache" >nul 2>&1
start http://localhost:8000
echo.
echo PDF Filler is starting at http://localhost:8000
echo Close this window to stop the server.
echo.
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
