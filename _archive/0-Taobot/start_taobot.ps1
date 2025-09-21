Param(
  [int]$Port = 8000,
  [string]$ProjectDir = "F:\Braindump\2025\0-Taobot",
  [switch]$NoNeo4j
)

Set-Location -Path $ProjectDir

# Create logs folder
$newLogDir = Join-Path $ProjectDir "logs"
if (!(Test-Path $newLogDir)) { New-Item -ItemType Directory -Path $newLogDir | Out-Null }
$logFile = Join-Path $newLogDir ("start_agent_" + (Get-Date -Format "yyyy-MM-dd_HH-mm-ss") + ".log")

# Ensure virtual env
$venvPath = Join-Path $ProjectDir ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
if (!(Test-Path $venvPython)) {
  Write-Host "Creating virtual environment at $venvPath ..."
  py -m venv $venvPath
}

# Activate venv
$activate = Join-Path $venvPath "Scripts\Activate.ps1"
. $activate

# requirements.txt (create if missing)
if (!(Test-Path ".\requirements.txt")) {
@"
fastapi
uvicorn
pydantic
python-dotenv
neo4j
requests
"@ | Out-File -FilePath ".\requirements.txt" -Encoding UTF8 -Force
}

# Install dependencies
if ($NoNeo4j) {
  Write-Host "Installing core deps (without neo4j)..."
  pip install fastapi uvicorn pydantic python-dotenv requests
} else {
  Write-Host "Installing deps (including neo4j)..."
  pip install -r requirements.txt
}

# Ensure .env exists and set API_PORT
$envPath = Join-Path $ProjectDir ".env"
if (!(Test-Path $envPath)) {
@"
# --- Taobot environment ---
# Optional Neo4j settings:
# NEO4J_URI=bolt://localhost:7687
# NEO4J_USER=neo4j
# NEO4J_PASSWORD=changeme

API_PORT=$Port
"@ | Out-File -FilePath $envPath -Encoding UTF8 -Force
  Write-Host "Created .env with defaults."
} else {
  $env:API_PORT = "$Port"
}

Write-Host "Starting Taobot orchestrator on http://127.0.0.1:$Port ..."
$env:API_PORT = "$Port"
python start_agent.py --mode both --api-port $Port 2>&1 | Tee-Object -FilePath $logFile
