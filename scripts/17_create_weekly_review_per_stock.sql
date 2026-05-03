-- 17_create_weekly_review_per_stock.sql
-- 라운드: 2026-05 weekly-review overhaul
-- weekly_reviews(주간 종합) 와 별개로 종목별 회고를 영속화.
-- per-stock-analysis 7-step 의 회고 평행 — base_impact 4분류 + foregone_pnl 정량 추적.
-- 1주 1 종목 1 row, 같은 (user_id, week_start, code) 는 upsert.
-- ====================================================================

CREATE TABLE IF NOT EXISTS weekly_review_per_stock (
  user_id     UUID NOT NULL REFERENCES users(id),
  week_start  DATE NOT NULL,                  -- 월요일 (KST)
  week_end    DATE NOT NULL,                  -- 일요일 (KST)
  code        TEXT NOT NULL REFERENCES stocks(code),

  -- 매매 평가 (foregone_pnl + smart_or_early 자동 분류)
  trade_evaluations JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- [{trade_id, side, sold_at|bought_at, price, current_price, qty,
    --   foregone_pnl, delta_pct, smart_or_early}]

  -- base 영향 4분류 (decisive/supportive/contradictory/neutral)
  base_snapshot JSONB,
    -- {economy: {...}, industry: {...}, stock: {...}} 회고 시점 메타
  base_impact TEXT
    CHECK (base_impact IN ('decisive','supportive','contradictory','neutral')
           OR base_impact IS NULL),
  base_thesis_aligned BOOLEAN,
    -- base.thesis 와 본 주 실제 결과 정합 여부
  base_refresh_required BOOLEAN NOT NULL DEFAULT FALSE,
    -- 만기 임박 또는 narrative 수정 필요
  base_refreshed_during_review BOOLEAN NOT NULL DEFAULT FALSE,
    -- Phase 0 에서 본 종목 base 갱신했는지
  base_appendback_done BOOLEAN NOT NULL DEFAULT FALSE,
    -- Phase 3 에서 base.Daily Appended Facts append 했는지
  base_narrative_revision_proposed BOOLEAN NOT NULL DEFAULT FALSE,
    -- decisive 강화 발견 시 narrative 수정 후보 큐 적재 여부

  content TEXT,                              -- 자연어 본문 (200~400자)
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

  PRIMARY KEY (user_id, week_start, code)
);

-- 트리거 — updated_at 자동 갱신 (set_updated_at 함수는 schema.sql 에서 정의됨)
DROP TRIGGER IF EXISTS trg_weekly_review_per_stock_updated ON weekly_review_per_stock;
CREATE TRIGGER trg_weekly_review_per_stock_updated
  BEFORE UPDATE ON weekly_review_per_stock
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
