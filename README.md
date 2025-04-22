# SNS Poster App

複数のSNSプラットフォームに同時投稿できるWebアプリケーション。

画像・動画投稿や予約投稿にも対応した多機能SNS投稿管理ツールです。

<img src="https://github.com/user-attachments/assets/383cb79c-79cc-40c8-b43c-af3ce3113c34" width="760" height="auto" style="display:inline-block; margin:20px 0px">

## 概要

SNS Poster Appは、複数のSNSアカウント（Bluesky、X/Twitter、Threads、Misskey、Mastodon）を連携させ、一度の操作で複数のプラットフォームに同時投稿できるアプリケーションです。Docker環境で簡単に起動でき、各SNSの文字数制限に対応した投稿フォームを備えています。

## 機能

- **複数SNSへの同時投稿**: 5つのプラットフォーム（Bluesky、X/Twitter、Threads、Misskey、Mastodon）対応
- **文字数制限チェック**: 各SNSの文字数制限に合わせたリアルタイムチェック
- **一括/個別投稿モード**: 全プラットフォームに同じ内容を投稿するか、プラットフォームごとに異なる内容を投稿するかを選択可能
- **画像/動画投稿**: 最大4つまでのメディアファイルをアップロードして投稿可能(一部のSNSでは制限されるため投稿ができないため注意が必要です。)
- **予約投稿機能**: 指定した日時に自動投稿するスケジュール機能
- **プラットフォーム選択UI**: チェックボックスでSNSを個別に選択可能
- **Docker対応**: コンテナ化されており、環境に依存せず簡単に起動可能
- **DarkMode対応**: 使いやすいUIに設計しています

## システム要件

- Docker および Docker Compose
- インターネット接続（各SNS APIへのアクセス用）
- PostgreSQLデータベース（Docker Composeで自動設定）

## インストールと起動方法

### 1. リポジトリのクローン

```bash
git clone https://github.com/naomina121/sns_poster_app.git
cd sns_poster_app
```

### 2. 環境変数の設定

`backend/.env.example`ファイルを`backend/.env`としてコピーし、各SNSの認証情報を設定します：

```bash
cp backend/.env.example backend/.env
```

`.env`ファイルを編集して、以下の項目を設定してください：

```
# Bluesky
BLUESKY_USERNAME=あなたのBlueskyユーザー名
BLUESKY_PASSWORD=あなたのBlueskyパスワード

# X/Twitter
X_API_KEY=TwitterのAPIキー
X_API_SECRET=TwitterのAPIシークレット
X_ACCESS_TOKEN=Twitterのアクセストークン
X_ACCESS_TOKEN_SECRET=Twitterのアクセストークンシークレット

# Threads (via Instagram API)
THREADS_ACCESS_TOKEN=Threadsのアクセストークン

# Misskey
MISSKEY_API_TOKEN=MisskeyのAPIトークン
MISSKEY_INSTANCE_URL=https://misskey.io/（または利用するインスタンスのURL）

# Mastodon
MASTODON_ACCESS_TOKEN=Mastodonのアクセストークン
MASTODON_INSTANCE_URL=https://mastodon.social/（または利用するインスタンスのURL）

# Flask設定（セキュリティのためランダムな文字列を設定）
FLASK_SECRET_KEY=ランダムな文字列（例：openssl rand -hex 24 で生成）

# Cloudinary設定（Threadsへの画像投稿に使用）
CLOUDINARY_CLOUD_NAME=あなたのCloudinary名
CLOUDINARY_API_KEY=CloudinaryのAPIキー
CLOUDINARY_API_SECRET=CloudinaryのAPIシークレット

# データベース設定（Docker Compose環境では変更不要）
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/sns_poster
```

### 3. Dockerでの起動

```bash
docker-compose up --build -d
```

### 4. アプリケーションへのアクセス

ブラウザで以下のURLにアクセスします：

```
http://localhost:5001
```

## 使用方法

1. **SNSプラットフォームの選択**:
   - 投稿したいSNSプラットフォームをクリックして選択します
   - 連携していないプラットフォームはグレーアウト表示され選択できません

2. **投稿モードの選択**:
   - **一括投稿モード**: すべてのプラットフォームに同じ内容を投稿
   - **個別投稿モード**: 各プラットフォームに異なる内容を投稿

3. **投稿内容の入力**:
   - 文字数制限はリアルタイムで表示され、制限に近づくと警告が表示されます
   - 一括投稿モードでは、最も小さい文字数制限が適用されます

4. **メディアの追加（オプション）**:
   - 「画像追加」セクションにファイルをドラッグ＆ドロップするか、クリックして選択
   - 最大4つまでのメディアファイル（画像/動画）を追加可能

5. **予約投稿の設定（オプション）**:
   - 「投稿予約」をチェックして日時を指定
   - 現在より未来の時間を選択する必要があります

6. **投稿**:
   - 「投稿する」ボタンをクリックして投稿を実行
   - 通常投稿は即時に実行され、予約投稿は指定した時間に実行されます
   - 投稿結果は画面下部に表示されます

7. **予約済み投稿の管理**:
   - 「予約済み投稿一覧」セクションで予約した投稿を確認
   - 不要な予約投稿は「削除」ボタンから削除可能

## ファイル構成

```
sns_poster_app/
 ├── backend/                # バックエンド（Flask）
 │   ├── app.py             # Flaskアプリケーションのメインコード
 │   ├── models.py          # データベースモデル（予約投稿管理用）
 │   ├── scheduler.py       # 予約投稿実行スケジューラー
 │   ├── utils.py           # SNS API連携用の補助関数
 │   ├── requirements.txt   # 必要なPythonライブラリのリスト
 │   ├── uploads/           # アップロードされたメディアファイルの保存先
 │   └── .env               # 環境変数（APIキーなど）
 ├── frontend/              # フロントエンド
 │   ├── index.html         # メインのHTMLファイル
 │   ├── script.js          # フロントエンド用JavaScriptコード
 │   ├── style.css          # 標準テーマCSS
 │   ├── style_dark_hls.css # ダークモード用CSS
 │   └── img/               # 画像リソース
 ├── Dockerfile             # Dockerイメージ構築用設定
 ├── docker-compose.yml     # Docker Compose設定
 └── .gitignore             # Git除外設定
```

## 技術スタック

- **バックエンド**:
  - Flask (Python)
  - SQLAlchemy + PostgreSQL（予約投稿管理用）
  - 各SNS用APIライブラリ:
    - atproto: Bluesky用
    - tweepy: X/Twitter用
    - misskey.py: Misskey用
    - mastodon.py: Mastodon用
  - Cloudinary（Threadsへの画像投稿用）

- **フロントエンド**:
  - HTML5
  - CSS3
  - JavaScript (ES6+)

- **インフラ**:
  - Docker
  - Docker Compose
  - PostgreSQL

## API対応状況

| プラットフォーム | API状況 | 備考 |
|--------------|---------|------|
| Bluesky      | 公式API | atproto ライブラリを使用 |
| X / Twitter  | 公式API | tweepy ライブラリを使用 |
| Threads      | 非公式API | Threads APIを利用 |
| Misskey      | 公式API | misskey.py ライブラリを使用 |
| Mastodon     | 公式API | mastodon.py ライブラリを使用 |

## 注意事項

- 各SNSのAPIキーや個人認証情報は`.env`ファイルで管理し、Gitリポジトリにはコミットしないでください
- 各SNSプラットフォームのAPI利用制限に注意してください
- 本番環境で使用する際は、適切なセキュリティ対策を施してください
- 予約投稿機能はサーバーが稼働している間のみ実行されます

## カスタマイズ方法

### 新しいSNSプラットフォームの追加

1. `utils.py`の`CHARACTER_LIMITS`辞書に新しいプラットフォームと文字数制限を追加
2. `SnsClient`クラスに新しいクライアント初期化と投稿メソッドを実装
3. `app.py`のAPI処理に新プラットフォームを追加
4. フロントエンドのUIを更新

### 実装アイデア

- 投稿分析ダッシュボード
- ハッシュタグやメンション補完機能
- 投稿テンプレート保存機能
- 定期投稿機能

## トラブルシューティング

### よくある問題と解決方法

- **アプリが起動しない場合**:
  - Dockerのログを確認: `docker-compose logs -f`
  - PostgreSQLコンテナが正常に起動しているか確認
  - ポート5001が他のアプリケーションで使用されていないか確認

- **SNSへの投稿が失敗する場合**:
  - `.env`ファイルのAPI認証情報が正しいか確認
  - 各SNSのAPIレート制限を超えていないか確認
  - ログで詳細なエラーメッセージを確認

- **予約投稿が実行されない場合**:
  - スケジューラーログを確認（`docker-compose logs -f` でスケジューラーのログも表示）
  - サーバー時刻と予約時刻が正しいか確認
  - データベース接続が正常か確認

## ライセンス

このプロジェクトは[MITライセンス](LICENSE)の下で公開されています。

---

各SNSのAPIキーの取得方法については、各プラットフォームの開発者向けドキュメントを参照してください。
