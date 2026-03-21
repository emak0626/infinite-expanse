# Ollama 最適化設定スクリプト
# このスクリプトは、Windows環境でOllamaの安定性と並列処理能力を向上させるための環境変数を設定します。

$envVars = @{
    "OLLAMA_NUM_PARALLEL"     = "4"          # 並列リクエストを許可 (GPUメモリに合わせて調整)
    "OLLAMA_MAX_LOADED_MODELS" = "1"          # VRAMの断片化を防ぐため、1つのモデルのみロード
    "OLLAMA_KEEP_ALIVE"        = "24h"        # モデルを長時間VRAMに保持 (初回以降の応答を高速化)
    "OLLAMA_HOST"              = "0.0.0.0"    # Docker等からの外部接続を許可
}

Write-Host "--- Ollama 最適化設定の適用 ---" -ForegroundColor Cyan

foreach ($name in $envVars.Keys) {
    $value = $envVars[$name]
    Write-Host "設定中: $name = $value"
    [Environment]::SetEnvironmentVariable($name, $value, [EnvironmentVariableTarget]::User)
}

Write-Host "`n[重要] 設定を反映させるために、以下の手順を必ず行ってください：" -ForegroundColor Yellow
Write-Host "1. タスクバーの Ollama アイコンを右クリックして 'Quit Ollama' を選択"
Write-Host "2. 再度 Ollama を起動"
Write-Host "`n設定が完了しました。" -ForegroundColor Green
