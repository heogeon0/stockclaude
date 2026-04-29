-- =====================================================================
-- Phase 3 확장 스키마
-- =====================================================================
-- 1) score_weights: 타임프레임별 default + 종목별 override + 이력
-- 2) macro_series: FRED 시계열 캐시 (금리·환율·유가·VIX)
-- 3) dividend_events: 배당 이력·스케줄
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- 1. Score Weights
-- ---------------------------------------------------------------------
CREATE TABLE score_weight_defaults (
  timeframe TEXT NOT NULL CHECK (timeframe IN ('day-trade','swing','long-term','momentum')),
  dim       TEXT NOT NULL CHECK (dim IN ('재무','산업','경제','기술','밸류에이션')),
  weight    NUMERIC(3,2) NOT NULL CHECK (weight BETWEEN 0 AND 1),
  PRIMARY KEY (timeframe, dim)
);

-- 기존 skill 상수 seed
INSERT INTO score_weight_defaults (timeframe, dim, weight) VALUES
  ('day-trade', '재무', 0.10), ('day-trade', '산업', 0.15), ('day-trade', '경제', 0.15),
  ('day-trade', '기술', 0.55), ('day-trade', '밸류에이션', 0.05),
  ('swing',     '재무', 0.30), ('swing',     '산업', 0.25), ('swing',     '경제', 0.20),
  ('swing',     '기술', 0.05), ('swing',     '밸류에이션', 0.20),
  ('long-term', '재무', 0.35), ('long-term', '산업', 0.20), ('long-term', '경제', 0.15),
  ('long-term', '기술', 0.00), ('long-term', '밸류에이션', 0.30),
  ('momentum',  '재무', 0.15), ('momentum',  '산업', 0.25), ('momentum',  '경제', 0.15),
  ('momentum',  '기술', 0.40), ('momentum',  '밸류에이션', 0.05);

CREATE TABLE score_weight_overrides (
  code       TEXT NOT NULL REFERENCES stocks(code),
  timeframe  TEXT NOT NULL,
  dim        TEXT NOT NULL,
  weight     NUMERIC(3,2) NOT NULL CHECK (weight BETWEEN 0 AND 1),
  reason     TEXT,
  source     TEXT CHECK (source IN ('user','claude','backtest')),
  expires_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (code, timeframe, dim),
  CONSTRAINT fk_swo_dim  FOREIGN KEY (timeframe, dim)
    REFERENCES score_weight_defaults(timeframe, dim)
);

CREATE TABLE score_weight_history (
  id          BIGSERIAL PRIMARY KEY,
  code        TEXT,
  timeframe   TEXT, dim TEXT,
  old_weight  NUMERIC(3,2),
  new_weight  NUMERIC(3,2),
  reason      TEXT, source TEXT,
  changed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_swh_code_time ON score_weight_history(code, changed_at DESC);

-- override 변경 시 히스토리 자동 기록
CREATE OR REPLACE FUNCTION log_score_weight_change()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO score_weight_history (code, timeframe, dim, old_weight, new_weight, reason, source)
  VALUES (
    COALESCE(NEW.code, OLD.code),
    COALESCE(NEW.timeframe, OLD.timeframe),
    COALESCE(NEW.dim, OLD.dim),
    OLD.weight, NEW.weight,
    NEW.reason, NEW.source
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_swo_history
  AFTER INSERT OR UPDATE OR DELETE ON score_weight_overrides
  FOR EACH ROW EXECUTE FUNCTION log_score_weight_change();

-- 종목 × 타임프레임에 적용되는 최종 가중치 (override 있으면 그걸, 없으면 default)
CREATE OR REPLACE FUNCTION get_applied_weights(p_code TEXT, p_timeframe TEXT)
RETURNS TABLE(dim TEXT, weight NUMERIC(3,2), source TEXT) AS $$
  SELECT
    d.dim,
    COALESCE(o.weight, d.weight) AS weight,
    CASE
      WHEN o.weight IS NOT NULL
           AND (o.expires_at IS NULL OR o.expires_at > now())
      THEN o.source
      ELSE 'default'
    END AS source
  FROM score_weight_defaults d
  LEFT JOIN score_weight_overrides o
    ON o.code = p_code AND o.timeframe = p_timeframe AND o.dim = d.dim
   AND (o.expires_at IS NULL OR o.expires_at > now())
  WHERE d.timeframe = p_timeframe;
$$ LANGUAGE sql STABLE;

-- ---------------------------------------------------------------------
-- 2. Macro Series (FRED 시계열 캐시)
-- ---------------------------------------------------------------------
CREATE TABLE macro_series (
  series_id TEXT NOT NULL,                  -- 'DFF', 'DEXKOUS', 'VIXCLS', 'DCOILBRENTEU' 등
  date      DATE NOT NULL,
  value     NUMERIC(18,6),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (series_id, date)
);
CREATE INDEX idx_macro_date ON macro_series(date DESC);

-- 시리즈 메타데이터 (이름·단위 등)
CREATE TABLE macro_series_meta (
  series_id   TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  units       TEXT,
  frequency   TEXT,                          -- 'Daily', 'Monthly', 'Quarterly'
  category    TEXT,                          -- 'rate', 'fx', 'commodity', 'volatility'
  source      TEXT DEFAULT 'FRED'
);

-- 자주 쓰는 시리즈 seed
INSERT INTO macro_series_meta (series_id, name, units, frequency, category) VALUES
  ('DFF',           'Federal Funds Effective Rate',            '%',       'Daily', 'rate'),
  ('DEXKOUS',       'KRW/USD Exchange Rate',                   'KRW',     'Daily', 'fx'),
  ('VIXCLS',        'CBOE Volatility Index',                   'index',   'Daily', 'volatility'),
  ('DCOILBRENTEU',  'Brent Crude Oil Price',                   'USD/bbl', 'Daily', 'commodity'),
  ('DGS10',         'US 10-Year Treasury Yield',               '%',       'Daily', 'rate'),
  ('T10Y2Y',        'US 10Y-2Y Spread',                        '%',       'Daily', 'rate');

-- ---------------------------------------------------------------------
-- 3. Dividend Events
-- ---------------------------------------------------------------------
CREATE TABLE dividend_events (
  id          BIGSERIAL PRIMARY KEY,
  code        TEXT NOT NULL REFERENCES stocks(code),
  event_type  TEXT NOT NULL CHECK (event_type IN ('announced','ex_date','payment','reinvestment')),
  event_date  DATE NOT NULL,
  amount      NUMERIC(18,4),                -- 주당 배당금
  currency    TEXT DEFAULT 'KRW' CHECK (currency IN ('KRW','USD')),
  payout_ratio NUMERIC(6,2),
  yield_pct   NUMERIC(6,2),                 -- 배당수익률 (발표 시점 주가 기준)
  source      TEXT,                         -- 'DART','KIS','manual'
  notes       TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (code, event_type, event_date)
);
CREATE INDEX idx_div_code_date ON dividend_events(code, event_date DESC);
CREATE INDEX idx_div_event_date ON dividend_events(event_date DESC);

COMMIT;

-- ---------------------------------------------------------------------
-- 검증
-- ---------------------------------------------------------------------
-- SELECT * FROM score_weight_defaults ORDER BY timeframe, dim;
-- SELECT * FROM get_applied_weights('000660', 'swing');
-- SELECT * FROM macro_series_meta;
