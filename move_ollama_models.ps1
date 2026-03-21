# Ollama Model Migration Script (Robust Version)
$sourcePath = "$HOME\.ollama\models"
$targetPath = "D:\OllamaModels"

Write-Host "--- Ollama Migration Tool ---"

# 1. Stop Ollama
Write-Host "[1/5] Stopping Ollama..."
$ollamaProc = Get-Process ollama -ErrorAction SilentlyContinue
if ($ollamaProc) {
    Stop-Process -Name ollama -Force
    Start-Sleep -Seconds 2
}

# 2. Create target directory
Write-Host "[2/5] Creating $targetPath..."
if (!(Test-Path $targetPath)) {
    New-Item -ItemType Directory -Path $targetPath -Force | Out-Null
}

# 3. Move models
if (Test-Path $sourcePath) {
    Write-Host "[3/5] Moving models..."
    Move-Item -Path "$sourcePath\*" -Destination $targetPath -Force -ErrorAction SilentlyContinue
}

# 4. Set Environment Variable
Write-Host "[4/5] Setting OLLAMA_MODELS..."
[Environment]::SetEnvironmentVariable("OLLAMA_MODELS", $targetPath, "User")
$env:OLLAMA_MODELS = $targetPath

# 5. Done
Write-Host "[5/5] Migration Complete!"
Write-Host "Please restart Ollama and your terminal/app."
