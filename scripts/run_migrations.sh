#!/usr/bin/env bash
# run_migrations.sh
# Railway release-phase 자동 migration 실행기.
#
# 동작:
#   1. schema_migrations 추적 테이블 보장 (없으면 생성)
#   2. scripts/[0-9]*.sql 을 정렬 순서로 순회
#   3. 적용 안된 파일만 psql 로 실행 + schema_migrations 에 기록
#
# 모든 migration sql 은 idempotent (IF NOT EXISTS) 패턴이지만, 추적 테이블로
# 이중 안전성 + 적용 이력 추적.
#
# Procfile:
#   release: bash scripts/run_migrations.sh
#
# 로컬 테스트:
#   DATABASE_URL=postgresql://... bash scripts/run_migrations.sh
set -euo pipefail

if [ -z "${DATABASE_URL:-}" ]; then
  echo "❌ DATABASE_URL 환경변수가 설정되어 있지 않습니다."
  exit 1
fi

# psql 이 있는지 확인 (Railway 에선 nixpacks.toml 이 postgresql-client 설치)
if ! command -v psql >/dev/null 2>&1; then
  echo "❌ psql 이 PATH 에 없습니다. nixpacks.toml 의 postgresql-client 설치 확인."
  exit 1
fi

echo "→ DATABASE: ${DATABASE_URL%%@*}@<host>"

# 1) 추적 테이블 보장
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 <<-'SQL'
CREATE TABLE IF NOT EXISTS schema_migrations (
  filename TEXT PRIMARY KEY,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
SQL

# 2) 미적용 sql 파일 순회 + 적용
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

applied_count=0
skipped_count=0

for sql_path in "$SCRIPT_DIR"/[0-9]*.sql; do
  [ -e "$sql_path" ] || continue
  base="$(basename "$sql_path")"

  applied="$(psql "$DATABASE_URL" -tAc "SELECT 1 FROM schema_migrations WHERE filename='$base';" || echo "")"

  if [ "$applied" = "1" ]; then
    echo "  ✓ $base 이미 적용 (skip)"
    skipped_count=$((skipped_count + 1))
    continue
  fi

  echo "  → $base 적용 중..."
  if psql "$DATABASE_URL" -v ON_ERROR_STOP=1 < "$sql_path"; then
    psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -c "INSERT INTO schema_migrations (filename) VALUES ('$base');"
    echo "  ✓ $base 적용 완료"
    applied_count=$((applied_count + 1))
  else
    echo "  ❌ $base 적용 실패"
    exit 1
  fi
done

echo
echo "✅ migration 완료 — 신규 적용 ${applied_count}건, 스킵 ${skipped_count}건"
