#!/bin/bash
# PostgreSQLが起動するまで待機するスクリプト

set -e

host="$1"
shift
cmd="$@"

echo "PostgreSQLの接続を確認しています: ホスト=$host, ユーザー=postgres, データベース=sns_poster"

until PGPASSWORD=postgres psql -h "$host" -U "postgres" -p 5432 -d "sns_poster" -c '\q'; do
  >&2 echo "PostgreSQLの起動を待っています..."
  sleep 1
done

>&2 echo "PostgreSQLが起動しました - コマンドを実行します: $cmd"
exec $cmd
