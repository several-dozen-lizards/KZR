@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo [KayZero] Bootstrapping environment...

:: Create venv if missing
if not exist ".venv\Scripts\python.exe" (
  echo [KayZero] Creating virtual environment...
  py -3 -m venv .venv
  if errorlevel 1 (
    echo [ERROR] Failed to create venv. Install Python 3 and the 'py' launcher.
    goto :end
  )
)

call ".venv\Scripts\activate.bat"

:: Upgrade pip quietly
python -m pip install --upgrade pip >nul 2>&1

:: Install requirements (use file if present, else a sane default set)
if exist "requirements.txt" (
  echo [KayZero] Installing from requirements.txt...
  pip install -r requirements.txt
) else (
  echo [KayZero] Installing default dependencies...
  pip install fastapi uvicorn[standard] pydantic openai python-docx chromadb
)

:: Load .env if present (trims spaces and strips quotes)
if exist ".env" (
  echo [KayZero] Loading .env...
  for /f "usebackq eol=# tokens=* delims=" %%L in (".env") do (
    set "line=%%L"
    if not "!line!"=="" (
      for /f "tokens=1,* delims==" %%A in ("!line!") do (
        set "k=%%A"
        set "v=%%B"
        rem trim leading spaces
        for /f "tokens=* delims= " %%K in ("!k!") do set "k=%%K"
        for /f "tokens=* delims= " %%V in ("!v!") do set "v=%%V"
        rem strip surrounding quotes
        if defined v if "!v:~0,1!"=="\"" set "v=!v:~1!"
        if defined v if "!v:~-1!"=="\"" set "v=!v:~0,-1!"
        if defined k if defined v set "!k!=!v!"
      )
    )
  )
)

:: Helpful defaults
if "%HOST%"=="" set "HOST=127.0.0.1"
if "%PORT%"=="" set "PORT=8000"
set "CHROMADB_DISABLE_TELEMETRY=1"

if "%OPENAI_API_KEY%"=="" (
  echo [WARN] OPENAI_API_KEY not set. Running in offline echo mode.
) else (
  echo [KayZero] OPENAI_API_KEY detected.
)

:: Mode selection: default web. Usage: start_kay.bat [web|cli]
set "MODE=%~1"
if "%MODE%"=="" set "MODE=web"

if /I "%MODE%"=="web" (
  echo [KayZero] Starting Web UI at http://%HOST%:%PORT%/  (Ctrl+C to stop)
  start "" "http://%HOST%:%PORT%/"
  uvicorn server:app --host "%HOST%" --port "%PORT%" --log-level info
  goto :end
)

if /I "%MODE%"=="cli" (
  echo [KayZero] Starting CLI. (Ctrl+C to exit)
  python app.py
  goto :end
)

echo [KayZero] Unknown mode "%MODE%". Use: start_kay.bat [web|cli]

:end
echo.
