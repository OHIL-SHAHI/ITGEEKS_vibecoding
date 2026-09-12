Write-Host "[ITGEEKS] Starting Exam-Night Multimodal RAG Study Companion..." -ForegroundColor Cyan

# 1. Start Docker Containers (Qdrant & MongoDB)
Write-Host "[1/3] Ensuring Qdrant and MongoDB containers are running..." -ForegroundColor Yellow
docker compose up -d | Out-Null

# Wait for Qdrant and MongoDB to be reachable
$retries = 0
while ($retries -lt 15) {
    try {
        $res = Invoke-WebRequest -Uri "http://localhost:6333/collections" -UseBasicParsing -TimeoutSec 2
        if ($res.StatusCode -eq 200) { break }
    } catch {}
    Start-Sleep -Seconds 1
    $retries++
}

# 2. Start FastAPI Backend on port 8000
Write-Host "[2/3] Starting FastAPI Backend on port 8000..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:PYTHONPATH = '$PSScriptRoot'; Set-Location '$PSScriptRoot'; .venv\Scripts\uvicorn.exe backend.app.main:app --host 0.0.0.0 --port 8000 --reload"

# 3. Start Vite Frontend on port 5173
Write-Host "[3/3] Starting React + Vite UI on port 5173..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$PSScriptRoot\frontend'; npm.cmd run dev"

# 4. Open Browser
Start-Sleep -Seconds 3
Write-Host "Opening application at http://localhost:5173..." -ForegroundColor Green
Start-Process "http://localhost:5173"

Write-Host "[ITGEEKS] System is fully operational." -ForegroundColor Green
