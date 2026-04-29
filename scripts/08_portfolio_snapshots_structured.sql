-- =====================================================================
-- 08: portfolio_snapshots 구조화 (v11 — 액션 플랜 자동 리마인드)
-- =====================================================================
-- 기존 portfolio_snapshots 테이블에 구조화 필드 4개 추가.
--   - per_stock_summary: 종목별 한 줄 요약 배열 (code/name/close/change_pct/pnl_pct/verdict/note)
--   - risk_flags:        집중도·과열 경고 배열 ({type, code?, scope?, level, detail})
--   - action_plan:       우선순위 액션 배열 ({priority, code, action, qty, trigger, condition, reason, status, executed_trade_id, expires_at})
--   - headline:          한 줄 결론 TEXT
-- 기존 summary_content 는 자유 서술용으로 유지.
-- 멱등: IF NOT EXISTS 로 재실행 안전.

ALTER TABLE portfolio_snapshots
  ADD COLUMN IF NOT EXISTS per_stock_summary JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS risk_flags        JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS action_plan       JSONB NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS headline          TEXT;

-- action_plan JSONB 내 status 필터 인덱스 (pending 조회 고속화)
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_action_status
  ON portfolio_snapshots USING GIN (action_plan jsonb_path_ops);
