@echo on
setlocal
cd /d "%~dp0"

if not exist "venv" py -m venv venv
call "venv\Scripts\activate.bat"

if exist requirements.txt (
  pip install -r requirements.txt
) else (
  pip install fastapi uvicorn pydantic openai python-docx
)

rem optional: quiet chroma telemetry
set CHROMADB_DISABLE_TELEMETRY=1


start "" "http://127.0.0.1:8000/"
python -u server.py
echo [exit code] %errorlevel%
pause
