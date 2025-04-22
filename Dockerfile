FROM python:3.10-slim

WORKDIR /app

# PostgreSQLのクライアントライブラリとビルドツールをインストール
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 必要なパッケージをインストール
COPY ./backend/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションのコードをコピー
COPY . /app/

# 環境変数の設定
ENV FLASK_APP=backend/app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5001

# ポートを公開
EXPOSE 5001
EXPOSE 5432

# PostgreSQLの起動を待つスクリプト
COPY ./backend/wait-for-postgres.sh /wait-for-postgres.sh
RUN chmod +x /wait-for-postgres.sh

# アプリケーションの実行
CMD ["/wait-for-postgres.sh", "postgres", "flask", "run"]
