-- 16_create_weekly_strategy.sql
-- v8 (2026-05): weekly_strategy 신규 테이블 — 5번째 모드 (사용자 + LLM 브레인스토밍)
-- 학습 사이클의 시작점: 매주 월요일 brainstorm → 일일 운영 (per-stock-analysis 인용) → 금/주말 weekly_review (전략 평가) → 다음 월요일 brainstorm
-- ====================================================================

CREATE TABLE IF NOT EXISTS weekly_strategy (
  id BIGSERIAL PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  week_start DATE NOT NULL,                 -- 월요일 (KST)
  market_outlook TEXT,                       -- 자연어 시장관 (cycle_phase 인용)
  focus_themes JSONB,                        -- ["반도체", "AI인프라"] 같은 식
  rules_to_emphasize JSONB,                  -- 강화 룰 ID list (rule_catalog)
  rules_to_avoid JSONB,                      -- 자제 룰 ID list (지난주 win-rate < 30%)
  position_targets JSONB,                    -- {신규: [...], 청산: [...], 비중: {kr, us}}
  risk_caps JSONB,                           -- {single_trade_pct, sector_max, cash_min}
  notes TEXT,                                -- 사용자 자율 코멘트
  brainstorm_log TEXT,                       -- LLM 제안 + 사용자 대화 로그 (전략 도출 과정 보존)
  approved_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  UNIQUE (user_id, week_start)
);

CREATE INDEX IF NOT EXISTS idx_weekly_strategy_user_date
  ON weekly_strategy (user_id, week_start DESC);
