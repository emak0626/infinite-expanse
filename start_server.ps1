# AI Stock Analysis System - Server Startup Script

Write-Host "--- Starting AI Stock Analysis System ---" -ForegroundColor Cyan

# 1. Initialize Database (SQLite)
Write-Host "Initializing Database..."
python init_db.py

# 2. Start FastAPI Server
Write-Host "Starting Server..."
Write-Host "Access locally at: http://localhost:8000" -ForegroundColor Green
uvicorn main:app --host 0.0.0.0 --port 8000
