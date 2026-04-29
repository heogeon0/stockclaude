#!/usr/bin/env bash
# 로컬 PG (Docker) → backups/db.sql
# 용도: git으로 DB 백업·이관 (Neon 이전 시 복원용)
set -euo pipefail

CONTAINER="${PG_CONTAINER:-stock-manger-pg}"
DB="${PG_DB:-stock_manger}"
USER="${PG_USER:-stock}"
OUT="$(dirname "$0")/../backups/db.sql"

mkdir -p "$(dirname "$OUT")"

docker exec "$CONTAINER" pg_dump -U "$USER" -d "$DB" \
  --format=plain --no-owner --no-acl --clean --if-exists \
  > "$OUT"

echo "✅ dumped → $OUT ($(wc -l < "$OUT") lines, $(du -h "$OUT" | cut -f1))"
