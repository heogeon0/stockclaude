-- =====================================================================
-- stock_base: 재무 지표 JSONB → 컬럼 승격
-- =====================================================================
-- 이유: 주요 재무 지표는 모든 상장주 공통 → 컬럼이 집계·인덱스·타입·BI 관점 유리
-- JSONB는 forward 추정치·업종 특수 지표용 `fundamentals_extra`로 용도 전환
-- =====================================================================

BEGIN;

-- 1) 신규 컬럼 추가
ALTER TABLE stock_base
  ADD COLUMN per              NUMERIC(8,2),
  ADD COLUMN pbr              NUMERIC(6,2),
  ADD COLUMN psr              NUMERIC(6,2),
  ADD COLUMN ev_ebitda        NUMERIC(6,2),
  ADD COLUMN roe              NUMERIC(6,2),
  ADD COLUMN roa              NUMERIC(6,2),
  ADD COLUMN op_margin        NUMERIC(6,2),
  ADD COLUMN net_margin       NUMERIC(6,2),
  ADD COLUMN debt_ratio       NUMERIC(6,2),
  ADD COLUMN eps              BIGINT,
  ADD COLUMN bps              BIGINT,
  ADD COLUMN dividend_yield   NUMERIC(6,2),
  ADD COLUMN market_cap       BIGINT;

-- 2) 기존 JSONB 데이터 → 컬럼 이관
UPDATE stock_base SET
  per        = NULLIF(fundamentals->>'per', '')::NUMERIC,
  pbr        = NULLIF(fundamentals->>'pbr', '')::NUMERIC,
  roe        = NULLIF(fundamentals->>'roe', '')::NUMERIC,
  op_margin  = NULLIF(fundamentals->>'op_margin', '')::NUMERIC;

-- 3) 이관한 키 제거 + 컬럼 이름 변경 (fundamentals → fundamentals_extra)
UPDATE stock_base SET
  fundamentals = fundamentals - 'per' - 'pbr' - 'roe' - 'op_margin';

ALTER TABLE stock_base RENAME COLUMN fundamentals TO fundamentals_extra;

-- 4) 인덱스 (자주 쓸 법한 재무 지표만)
CREATE INDEX idx_stock_base_per ON stock_base(per) WHERE per IS NOT NULL;
CREATE INDEX idx_stock_base_pbr ON stock_base(pbr) WHERE pbr IS NOT NULL;
CREATE INDEX idx_stock_base_roe ON stock_base(roe);

COMMIT;

-- =====================================================================
-- 검증
-- =====================================================================
-- SELECT code, per, pbr, roe, op_margin, fundamentals_extra FROM stock_base;
