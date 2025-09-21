@echo off
setlocal ENABLEDELAYEDEXECUTION
set PORT=%1
if "%PORT%"=="" set PORT=8000

set PROJECT=F:\Braindump\2025\0-Taobot
cd /d "%PROJECT%"

if exist start-taobot.ps1 (
  powershell -ExecutionPolicy Bypass -File "%PROJECT%\start-taobot.ps1" -Port %PORT%
) else (
  echo PowerShell script not found. Creating a minimal venv and starting...
  if not exist .venv (
    py -m venv .venv
  )
  call .venv\Scripts\activate.bat
  py -m pip install fastapi uvicorn pydantic python-dotenv
  set API_PORT=%PORT%
  python start_agent.py --mode both --api-port %PORT%
)
