#!/usr/bin/env bash
# backups/db.sql → 로컬 PG (Docker) 또는 임의 DATABASE_URL
#   기본: 로컬 Docker 컨테이너로 복원
#   DATABASE_URL 환경변수 있으면 해당 DB로 복원 (Neon 이식 등)
set -euo pipefail

IN="$(dirname "$0")/../backups/db.sql"

if [[ ! -f "$IN" ]]; then
  echo "❌ $IN 없음. 먼저 db_dump.sh 실행 후 clone 받거나 dump 파일 확인." >&2
  exit 1
fi

if [[ -n "${DATABASE_URL:-}" ]]; then
  echo "🌐 복원 → \$DATABASE_URL ($(wc -l < "$IN") lines)"
  psql "$DATABASE_URL" < "$IN"
else
  CONTAINER="${PG_CONTAINER:-stock-manger-pg}"
  DB="${PG_DB:-stock_manger}"
  USER="${PG_USER:-stock}"
  echo "🐳 복원 → docker $CONTAINER/$DB"
  docker exec -i "$CONTAINER" psql -U "$USER" -d "$DB" < "$IN"
fi

echo "✅ restored from $IN"
