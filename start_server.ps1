# AI Stock Analysis System - Server Startup Script

Write-Host "--- Starting AI Stock Analysis System ---" -ForegroundColor Cyan

# 1. Initialize Database (SQLite)
Write-Host "Initializing Database..."
python init_db.py

# 2. Start Infinite Expanse System (Docker)
Write-Host "Starting System via Docker Compose..." -ForegroundColor Green
docker compose up -d

Write-Host "------------------------------------------"
Write-Host "System is starting in the background."
Write-Host "Local Access: http://localhost:8000"
Write-Host "Mobile Access: http://192.168.100.27:8000" -ForegroundColor Cyan
Write-Host "------------------------------------------"
