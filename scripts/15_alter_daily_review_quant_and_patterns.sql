-- 15_alter_daily_review_quant_and_patterns.sql
-- v7 (2026-05): 결론 정량 컬럼 + learned_patterns 테이블 신설
-- G6 결정: 추론 = 자연어 (anchor 없음), 결론 = 정량 (추적/검증)
-- ====================================================================

-- 1) stock_daily 에 결론 정량 컬럼 추가
ALTER TABLE stock_daily
  ADD COLUMN IF NOT EXISTS size_pct INT;

ALTER TABLE stock_daily
  ADD COLUMN IF NOT EXISTS stop_method TEXT;

ALTER TABLE stock_daily
  DROP CONSTRAINT IF EXISTS stock_daily_stop_method_check;

ALTER TABLE stock_daily
  ADD CONSTRAINT stock_daily_stop_method_check
  CHECK (stop_method IN ('%','ATR') OR stop_method IS NULL);

ALTER TABLE stock_daily
  ADD COLUMN IF NOT EXISTS stop_value NUMERIC;

ALTER TABLE stock_daily
  ADD COLUMN IF NOT EXISTS override_dimensions JSONB;

ALTER TABLE stock_daily
  ADD COLUMN IF NOT EXISTS key_factors JSONB;

ALTER TABLE stock_daily
  ADD COLUMN IF NOT EXISTS referenced_rules JSONB;


-- 2) weekly_reviews 에 결론 정량 컬럼 추가
ALTER TABLE weekly_reviews
  ADD COLUMN IF NOT EXISTS rule_win_rates JSONB;

ALTER TABLE weekly_reviews
  ADD COLUMN IF NOT EXISTS pattern_findings JSONB;

ALTER TABLE weekly_reviews
  ADD COLUMN IF NOT EXISTS lessons_learned JSONB;

ALTER TABLE weekly_reviews
  ADD COLUMN IF NOT EXISTS next_week_emphasize JSONB;

ALTER TABLE weekly_reviews
  ADD COLUMN IF NOT EXISTS next_week_avoid JSONB;

ALTER TABLE weekly_reviews
  ADD COLUMN IF NOT EXISTS override_freq_30d JSONB;


-- 3) learned_patterns 신규 테이블
CREATE TABLE IF NOT EXISTS learned_patterns (
  id SERIAL PRIMARY KEY,
  tag TEXT UNIQUE NOT NULL,                 -- "earnings_d7_strict_stop" 같은 식별자
  description TEXT,                          -- 자연어 설명
  occurrences INT NOT NULL DEFAULT 1,
  win_rate NUMERIC,
  sample_count INT NOT NULL DEFAULT 0,
  first_seen DATE,
  last_seen DATE,
  promotion_status TEXT NOT NULL DEFAULT 'observation',
  related_rule_ids INT[],
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE learned_patterns
  DROP CONSTRAINT IF EXISTS learned_patterns_status_check;

ALTER TABLE learned_patterns
  ADD CONSTRAINT learned_patterns_status_check
  CHECK (promotion_status IN ('observation','rule_candidate','principle','user_principle'));

CREATE INDEX IF NOT EXISTS idx_learned_patterns_status
  ON learned_patterns (promotion_status, last_seen DESC);
