# migrate_to_onedrive.ps1
# Infinite Expanse プロジェクト移行スクリプト

# 1. ソースと宛先の定義
$sourceDir = $PSScriptRoot
# OneDriveのデフォルトパス。もしOneDriveのフォルダ名や場所が異なる場合は修正してください。
$destDir = "$env:OneDrive\Documents\InfiniteExpanse"

Write-Host "プロジェクトを以下の場所から移行します: $sourceDir"
Write-Host "移行先: $destDir"
Write-Host "--------------------------------------------------"

# 2. 宛先が存在するか確認し、なければ作成
if (-not (Test-Path -Path $destDir)) {
    Write-Host "移行先ディレクトリを作成しています..."
    New-Item -ItemType Directory -Force -Path $destDir | Out-Null
}

# 3. 除外設定
# コピーから除外するファイルとフォルダ（競合防止とサイズ削減のため）
$filesToExclude = @(
    "*.pyc",
    "*.pyo",
    "*.db",          # SQLiteデータベースを除外（データ保護のため）
    "*.sqlite",
    "*.sqlite3",
    ".env",          # シークレットを除外（安全のため、必要なら手動でコピーしてください）
    "migrate_to_onedrive.ps1" # スクリプト自体はコピー先に不要かもしれませんが、あっても問題ありません。
)

$foldersToExclude = @(
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "env",
    ".idea",
    ".vscode",       # IDE設定はPCごとに異なる可能性があるため除外します。
    "brain",         # Agentのアーティファクト。
    "logs",
    "data"           # DB用のdataフォルダがある場合
)

# 4. Robocopyによるコピー実行
# /MIR :: ディレクトリツリーをミラーリング（/E + /PURGE と同等）。
# /XD  :: 指定された名前/パスに一致するディレクトリを除外。
# /XF  :: 指定された名前/パスに一致するファイルを除外。
# /ZO  :: 再起動可能モード。
# /R:0 :: 失敗したコピーの再試行回数: 0
# /W:0 :: 再試行間の待機時間: 0

$robocopyArgs = @(
    "$sourceDir",
    "$destDir",
    "/MIR",
    "/XD", $foldersToExclude,
    "/XF", $filesToExclude,
    "/R:0",
    "/W:0"
)

Write-Host "コピー（Robocopy）を開始します..."
& robocopy @robocopyArgs

# 5. 完了後の指示
Write-Host "--------------------------------------------------"
Write-Host "移行が完了しました！"
Write-Host "次のフォルダを開いてください: $destDir"
Write-Host "必要に応じて .env ファイルを手動で作成・更新してください。"
Write-Host "今後は、VS Codeでこの新しいフォルダを開いて作業してください。"
if ($lastexitcode -lt 8) { Write-Host "Robocopy は正常に終了しました。" -ForegroundColor Green }
else { Write-Host "Robocopy はエラー（終了コード: $lastexitcode）で終了しました。" -ForegroundColor Red }
pause
