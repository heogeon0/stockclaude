# DB 마이그레이션 가이드

## 시나리오 1 — 신규 빈 DB 셋업

```bash
psql "$DATABASE_URL" < db/schema.sql                # 전체 스키마
psql "$DATABASE_URL" < db/seed.example.sql          # demo user + 기본 산업/종목
```

`db/schema.sql` 은 모든 alter 통합본. 신규 셋업에는 `scripts/*.sql` **불필요**.

## 시나리오 2 — 기존 운영 DB 마이그레이션 (옛 → 신 schema)

옛 dump 가 있을 때만. 순서 필수:

| 순서 | 파일 | 멱등? | 설명 |
|---|---|---|---|
| 1 | `01_*.sql` | — | (퍼블릭 레포에 미포함, 옛 private 전용) |
| 2 | `03_alter_stock_base_fundamentals.sql` | ✅ | stock_base 펀더멘털 컬럼 추가 |
| 3 | `05_alter_to_numeric.sql` | ✅ | 숫자 컬럼 타입 정합 |
| 4 | `07_score_weights_and_extras.sql` | ✅ | 스코어 가중치 + 확장 필드 |
| 5 | `08_portfolio_snapshots_structured.sql` | ✅ | snapshot 구조화 |
| 6 | `09_weekly_reviews.sql` | ✅ | 주간 회고 테이블 |
| 7 | `10_cash_balance_trigger.sql` | ✅ | 현금 잔고 자동 갱신 트리거 |
| 8 | `11_trades_rule_category.sql` | ✅ | 매매 룰 카테고리 컬럼 |
| 9 | `12_rule_category_add_earnings.sql` | ✅ | earnings 룰 enum 추가 |

`02_*` `04_*` `06_*` 는 옛 private 레포의 실 데이터 시드 (퍼블릭 레포 미포함).

## 시나리오 3 — 옛 운영 DB 풀 복원 (Railway 등)

`pg_dump` 풀 덤프를 그대로 원격 PG 에 import:

```bash
# 옛 로컬 DB → backup
bash scripts/db_dump.sh                              # backups/db.sql 생성

# Railway / Neon / 자가 호스팅에 그대로 복원
psql "$RAILWAY_DATABASE_URL" < backups/db.sql        # ~10초~수분
```

덤프는 `--clean --if-exists` 로 떠서 재실행 안전. schema + 데이터 + 트리거 모두 포함 (단일 트랜잭션 X).

## 백업

```bash
bash scripts/db_dump.sh                              # backups/db.sql 갱신
bash scripts/db_restore.sh                           # 같은 파일을 로컬에 복원
```

`backups/` 는 `.gitignore` 처리. 실 운영 데이터 외부 유출 X.
