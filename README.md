# 🚀 Infinite Expanse - 投資支援システム

AI（Google Gemini）とkabuステーション®APIを連携させた、株式市場の分析・銘柄スクリーニングシステムです。

## 🏗 技術スタック

| レイヤー | 技術 |
|---|---|
| バックエンド | Python / FastAPI |
| AI エンジン | Google Gemini API |
| 証券データ | kabuステーション® REST API |
| DB | TimescaleDB（PostgreSQL） |
| インフラ | Docker Compose |
| リモートアクセス | Tailscale |

## ⚡ クイックスタート

### 1. 前提条件

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) ＋ WSL2
- kabuステーション®（Windows側で起動済み）
- [Tailscale](https://tailscale.com/download)（外出先アクセス用）

### 2. 環境変数の設定

```powershell
copy .env.example .env
```

`.env` を開いて以下を設定：

```env
GEMINI_API_KEY=your_api_key_from_google_ai_studio
KABU_API_PASSWORD=your_kabu_password
MOCK_MODE=True          # 最初はTrue（テストモード）
KABU_API_HOST=host.docker.internal
KABU_API_PORT=18080
POSTGRES_HOST=timescaledb
POSTGRES_USER=user
POSTGRES_PASSWORD=password
POSTGRES_DB=stock_analysis
```

### 3. 起動

```powershell
# コンテナをビルド＆起動
docker compose up --build -d

# DB初期化（初回のみ）
docker compose exec app python init_db.py

# ログ確認
docker compose logs -f app
```

| アクセス先 | URL |
|---|---|
| ローカル | http://localhost:8000 |
| 外出先（Tailscale） | http://100.x.x.x:8000 |

## 📁 プロジェクト構成

```
infinite-expanse/
├── main.py              # FastAPI エントリポイント
├── analyzer_agent.py    # AI分析エージェント
├── scheduler.py         # 定時タスク（APScheduler）
├── screener.py          # 銘柄スクリーニング
├── kabu_api.py          # kabuステーション® APIクライアント
├── models.py            # データモデル（Pydantic）
├── models_db.py         # DBモデル（SQLAlchemy）
├── repository.py        # DBアクセス層
├── prompts.py           # Geminiプロンプト定義
├── strategy_config.py   # 投資戦略設定
├── config.py            # アプリ設定
├── database.py          # DB接続
├── docker-compose.yml   # コンテナ構成
├── Dockerfile           # アプリコンテナ定義
├── requirements.txt     # Python依存パッケージ
├── .env.example         # 環境変数テンプレート（.envは除外済み）
└── static/              # フロントエンド（JS/CSS）
```

## 🔒 セキュリティ注意事項

- `.env` は **絶対にコミットしない**（`.gitignore` で除外済み）
- APIキーはすべて `.env` で管理
- 本番運用時は `MOCK_MODE=False` に変更

## 🖥 新しいPCでのセットアップ

詳細は [SETUP_ON_NEW_PC.md](SETUP_ON_NEW_PC.md) を参照してください。

## 📊 主な機能

- **銘柄スクリーニング**: 設定した戦略に基づく自動スクリーニング
- **AI分析レポート**: Geminiによる詳細な市場分析レポート生成
- **リアルタイム価格取得**: kabuステーション® API連携
- **定時自動実行**: 場前・場中・場後の自動データ取得
- **Webダッシュボード**: ブラウザからアクセス可能なUI
