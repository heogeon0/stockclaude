-- ====================================================================
-- 09_weekly_reviews.sql
-- 주간 회고 전용 테이블. portfolio_snapshots(일일)와 분리:
--   - portfolio_snapshots = raw 일일 종합 (매일 1건)
--   - weekly_reviews     = 주간 학습/평가 derived (주 1건)
-- ====================================================================

CREATE TABLE IF NOT EXISTS weekly_reviews (
  id          BIGSERIAL PRIMARY KEY,
  user_id     UUID NOT NULL REFERENCES users(id),
  week_start  DATE NOT NULL,           -- 월요일 (KST)
  week_end    DATE NOT NULL,           -- 금요일 (KST)

  -- 성과 요약
  realized_pnl_kr     NUMERIC(16,2),   -- 주간 실현 KRW
  realized_pnl_us     NUMERIC(12,2),   -- 주간 실현 USD
  unrealized_pnl_kr   NUMERIC(16,2),   -- 주말 기준 미실현 KRW
  unrealized_pnl_us   NUMERIC(12,2),   -- 주말 기준 미실현 USD
  trade_count         INT NOT NULL DEFAULT 0,

  -- 학습/평가 (구조화)
  win_rate           JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- {strategy_name: {tries: N, wins: N, pct: float}}
  rule_evaluations   JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- [{rule, trade_id, pre_decision, post_outcome, foregone_pnl, smart_or_early}]
  highlights         JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- [{type: 'insight'|'pattern'|'warning', detail}]
  next_week_actions  JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- portfolio_snapshots.action_plan 과 같은 구조

  -- 자유 서술
  headline   TEXT,
  content    TEXT,                     -- 마크다운 본문

  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  UNIQUE (user_id, week_start)
);

CREATE INDEX IF NOT EXISTS idx_weekly_reviews_user_date
  ON weekly_reviews (user_id, week_start DESC);
