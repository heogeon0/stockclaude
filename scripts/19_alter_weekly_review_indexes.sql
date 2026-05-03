-- 19_alter_weekly_review_indexes.sql
-- 라운드: 2026-05 weekly-review overhaul
-- weekly_review_per_stock 조회 인덱스.
-- prepare_weekly_review_portfolio 의 list_by_week / 종목별 시계열 조회 최적화.
-- ====================================================================

-- (user_id, week_start DESC) — 최근 주 조회
CREATE INDEX IF NOT EXISTS idx_wrps_user_week
  ON weekly_review_per_stock (user_id, week_start DESC);

-- (user_id, code, week_start DESC) — 종목별 시계열 조회
CREATE INDEX IF NOT EXISTS idx_wrps_user_code_week
  ON weekly_review_per_stock (user_id, code, week_start DESC);

-- base_impact 분포 조회 (decisive/supportive/contradictory/neutral)
CREATE INDEX IF NOT EXISTS idx_wrps_base_impact
  ON weekly_review_per_stock (base_impact)
  WHERE base_impact IS NOT NULL;

-- base 갱신 필요한 종목만 조회 (Phase 3 분기 룰)
CREATE INDEX IF NOT EXISTS idx_wrps_base_refresh_required
  ON weekly_review_per_stock (user_id, week_start)
  WHERE base_refresh_required = TRUE;
