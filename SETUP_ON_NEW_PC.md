# マルチPC・セットアップガイド（Docker版）

このプロジェクトは **Docker Compose** を使用して環境を管理します。
新しいPCや再インストール後も、コンテナごと移行するだけで環境が再現できます。

---

## 1. 前提条件のインストール

| ソフトウェア | 用途 | インストール先 |
|---|---|---|
| Docker Desktop | コンテナ実行基盤 | https://www.docker.com/products/docker-desktop/ |
| WSL2 | Dockerバックエンド（Windows必須） | Docker Desktop インストール時に自動セットアップ |
| Tailscale | リモートアクセス用VPN | https://tailscale.com/download |
| Git | ソース管理 | https://git-scm.com/ |

---

## 2. 環境変数の設定（`.env`）

`.env` ファイルはセキュリティ上の理由から**同期されません**。新しいPCでは手動で作成してください。

```powershell
copy .env.example .env
```

`.env` を開き、以下を設定します：

```
GEMINI_API_KEY=your_api_key_from_google_ai_studio
MOCK_MODE=true                     # 最初はtrueで動作確認
KABU_API_HOST=host.docker.internal # DockerからWindowsホストのkabuステーションへ接続
KABU_API_PORT=18080
POSTGRES_HOST=timescaledb
POSTGRES_USER=user
POSTGRES_PASSWORD=password
POSTGRES_DB=stock_analysis
```

---

## 3. 起動手順

```powershell
# 1. コンテナをビルドして起動
docker compose up --build -d

# 2. DBの初期化（初回のみ）
docker compose exec app python init_db.py

# 3. ログの確認
docker compose logs -f app

# アクセス
# ローカル: http://localhost:8000
# 外出先:  http://100.x.x.x:8000 (TailscaleのIP)
```

---

## 4. kabuステーション® 連携（本番運用時）

`.env` で `MOCK_MODE=false` に変更する前に、以下を確認してください。

- kabuステーション® が **Windows側で起動済み** であること
- Docker内からのアクセスには `host.docker.internal:18080` を使用（`localhost` は不可）

---

## 5. 毎朝の自動復帰設定（Windows側）

kabuステーションは毎日 **4:30〜6:00** にセッション切断が発生します。

### 設定手順
1. **自動ログイン**: `Win + R` → `netplwiz` → ユーザーを選択してパスワード入力を省略
2. **kabuステーション自動起動**: `Win + R` → `shell:startup` → kabuステーションのショートカットを配置
3. **定時再起動**: タスクスケジューラで毎日 **6:05** に以下を実行：
   ```
   shutdown /r /f /t 0
   ```

---

## 6. 日々の開発ワークフロー（Antigravity）

1. Antigravity で `infinite-expanse` フォルダを開く
2. Agent Manager でタスクを作成（例: "GeminiのThinking APIを実装して"）
3. AIが生成した計画を確認・承認
4. Artifacts（テスト録画など）で動作確認
5. `git commit` && `git push` で GitHub に保存

---

## 7. トラブルシューティング

| 症状 | 対処 |
|---|---|
| `Connection refused` on port 5432 | `docker compose up -d timescaledb` でDBのみ先に起動 |
| `host.docker.internal` が解決できない | `docker-compose.yml` の `extra_hosts` 設定を確認 |
| kabuステーションAPIが返答しない | Windows側でkabuステーションが起動しているか確認 |
| DB初期化エラー | `docker compose exec app python init_db.py` を再実行 |

---

*Updated by Antigravity - v2 (Docker対応版)*
