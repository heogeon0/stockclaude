-- =====================================================================
-- stock-manager Schema v1.0
-- PostgreSQL 15+ / Railway & Supabase 호환
--
-- 설계 원칙:
--   1. 멀티테넌트 준비 (모든 유저 도메인 테이블 user_id FK)
--   2. 정확성 critical 데이터(trades·positions) 완전 구조화
--   3. 서술형 분석은 content TEXT (마크다운 보존)
--   4. 유연 메타키는 JSONB (쿼리·인덱싱 가능)
--   5. positions = trades 트리거로 자동 재계산 (수동 수정 불가)
--   6. 서버 = deterministic, Claude = reasoning 분업
-- =====================================================================

-- =====================================================================
-- Extensions
-- =====================================================================
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "btree_gin";  -- GIN + BTree 혼합 인덱스


-- =====================================================================
-- A. 유저 · 마스터
-- =====================================================================

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE,
  kis_app_key TEXT,
  kis_app_secret TEXT,
  kis_account_no TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE stocks (
  code TEXT PRIMARY KEY,
  market TEXT NOT NULL CHECK (market IN ('kr','us')),
  name TEXT NOT NULL,
  name_en TEXT,
  ticker TEXT,
  sector TEXT,
  industry_code TEXT,
  listing_market TEXT,
  currency TEXT NOT NULL DEFAULT 'KRW' CHECK (currency IN ('KRW','USD')),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','delisted')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_stocks_market ON stocks(market);
CREATE INDEX idx_stocks_industry ON stocks(industry_code);


-- =====================================================================
-- B. 거시 · 산업 (공용)
-- =====================================================================

-- 네이밍 규약:
--   KR     : '반도체', '전력설비' 등 (기존 skill 호환)
--   US     : 'us-semiconductors' 등 접두사 'us-'
--   Global : 'global-semiconductor' (market=NULL, parent 역할)
CREATE TABLE industries (
  code TEXT PRIMARY KEY,
  market TEXT CHECK (market IN ('kr','us') OR market IS NULL),
  name TEXT NOT NULL,
  name_en TEXT,
  parent_code TEXT REFERENCES industries(code),
  meta JSONB NOT NULL DEFAULT '{}'::jsonb,            -- {경기민감도, 밸류체인_위치, 규제환경, 성장단계, 경쟁구도}
  market_specific JSONB NOT NULL DEFAULT '{}'::jsonb, -- 시장별 특화 도피장
  score SMALLINT CHECK (score BETWEEN 0 AND 100),
  content TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ
);
CREATE INDEX idx_industries_market ON industries(market);
CREATE INDEX idx_industries_parent ON industries(parent_code);
CREATE INDEX idx_industries_meta ON industries USING GIN (meta);

-- stocks.industry_code 에 뒤늦게 FK 추가 (circular reference 방지)
ALTER TABLE stocks
  ADD CONSTRAINT fk_stocks_industry
  FOREIGN KEY (industry_code) REFERENCES industries(code);

CREATE TABLE economy_base (
  market TEXT PRIMARY KEY CHECK (market IN ('kr','us')),
  context JSONB NOT NULL DEFAULT '{}'::jsonb,         -- {금리_환경, 환율_수혜, 경기_사이클, 유동성, 지정학, 외국인_수급, VI_수준, ...}
  content TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ
);
CREATE INDEX idx_economy_base_context ON economy_base USING GIN (context);

CREATE TABLE economy_daily (
  market TEXT NOT NULL CHECK (market IN ('kr','us')),
  date DATE NOT NULL,
  index_values JSONB NOT NULL DEFAULT '{}'::jsonb,    -- KR:{kospi, kosdaq, vkospi} / US:{spy, qqq, vix, dxy}
  foreign_net BIGINT,
  institution_net BIGINT,
  context JSONB NOT NULL DEFAULT '{}'::jsonb,
  events JSONB NOT NULL DEFAULT '[]'::jsonb,          -- 당일 이벤트 요약
  content TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (market, date)
);
CREATE INDEX idx_economy_daily_date ON economy_daily(date DESC);
CREATE INDEX idx_economy_daily_context ON economy_daily USING GIN (context);


-- =====================================================================
-- C. 종목 분석 (base + daily + backtest + analyst)
-- =====================================================================

CREATE TABLE stock_base (
  code TEXT PRIMARY KEY REFERENCES stocks(code),
  -- Scoring (4차원)
  total_score SMALLINT CHECK (total_score BETWEEN 0 AND 100),
  financial_score SMALLINT,
  industry_score SMALLINT,
  economy_score SMALLINT,
  grade TEXT CHECK (grade IN ('Premium','Standard','Cautious','Defensive')),
  -- 밸류에이션 (NUMERIC: KR 원 + US 달러소수점 공용)
  fair_value_min      NUMERIC(18,4),
  fair_value_avg      NUMERIC(18,4),
  fair_value_max      NUMERIC(18,4),
  analyst_target_avg  NUMERIC(18,4),
  analyst_target_max  NUMERIC(18,4),
  analyst_consensus_count SMALLINT,
  -- 핵심 재무 지표 (모든 상장주 공통 — 컬럼)
  per             NUMERIC(8,2),                        -- Trailing P/E (적자 시 NULL)
  pbr             NUMERIC(6,2),
  psr             NUMERIC(6,2),
  ev_ebitda       NUMERIC(6,2),
  roe             NUMERIC(6,2),                        -- % (음수 가능)
  roa             NUMERIC(6,2),
  op_margin       NUMERIC(6,2),                        -- 영업이익률 %
  net_margin      NUMERIC(6,2),
  debt_ratio      NUMERIC(6,2),
  eps             NUMERIC(18,4),                       -- 주당 순이익
  bps             NUMERIC(18,4),
  dividend_yield  NUMERIC(6,2),
  market_cap      BIGINT,                              -- 시가총액 (분수 불필요, 큰 정수)
  -- 확장 지표 (forward 추정·업종 특수지표)
  fundamentals_extra JSONB NOT NULL DEFAULT '{}'::jsonb,  -- {per_forward_2026e, psr_2026e, bis_ratio, ffo, ...}
  -- 서술 섹션
  narrative TEXT,
  risks TEXT,
  scenarios TEXT,
  content TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ
);
CREATE INDEX idx_stock_base_grade ON stock_base(grade);
CREATE INDEX idx_stock_base_score ON stock_base(total_score DESC);
CREATE INDEX idx_stock_base_per ON stock_base(per) WHERE per IS NOT NULL;
CREATE INDEX idx_stock_base_pbr ON stock_base(pbr) WHERE pbr IS NOT NULL;
CREATE INDEX idx_stock_base_roe ON stock_base(roe);

CREATE TABLE stock_daily (
  user_id UUID NOT NULL REFERENCES users(id),
  code TEXT NOT NULL REFERENCES stocks(code),
  date DATE NOT NULL,
  -- OHLCV (NUMERIC 가격 + BIGINT 거래량)
  open  NUMERIC(18,4),
  high  NUMERIC(18,4),
  low   NUMERIC(18,4),
  close NUMERIC(18,4),
  volume BIGINT,
  -- 12개 지표
  rsi14 NUMERIC(5,2),
  stoch_k NUMERIC(5,2),
  stoch_d NUMERIC(5,2),
  adx NUMERIC(5,2),
  atr14 NUMERIC(14,2),
  macd NUMERIC(14,2),
  macd_signal NUMERIC(14,2),
  macd_hist NUMERIC(14,2),
  bb_upper  NUMERIC(18,4),
  bb_middle NUMERIC(18,4),
  bb_lower  NUMERIC(18,4),
  sma5   NUMERIC(18,4),
  sma20  NUMERIC(18,4),
  sma60  NUMERIC(18,4),
  sma120 NUMERIC(18,4),
  sma200 NUMERIC(18,4),
  ichimoku JSONB NOT NULL DEFAULT '{}'::jsonb,        -- {conv, base, span_a, span_b, lagging}
  -- 12개 시그널 결과
  signals JSONB NOT NULL DEFAULT '[]'::jsonb,         -- [{전략, 시그널, 조건, 진입가, 손절가, 가중치}, ...]
  verdict TEXT CHECK (verdict IN ('강한매수','매수우세','중립','매도우세','강한매도')),
  content TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, code, date)
);
CREATE INDEX idx_daily_date ON stock_daily(date DESC);
CREATE INDEX idx_daily_verdict ON stock_daily(verdict, date DESC);
CREATE INDEX idx_daily_signals ON stock_daily USING GIN (signals);

CREATE TABLE backtest_cache (
  code TEXT PRIMARY KEY REFERENCES stocks(code),
  result JSONB NOT NULL,                              -- {strategy: {win_rate, avg_return, weight}, ...}
  computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ
);

CREATE TABLE analyst_reports (
  id BIGSERIAL PRIMARY KEY,
  code TEXT NOT NULL REFERENCES stocks(code),
  broker TEXT NOT NULL,
  broker_country TEXT CHECK (broker_country IN ('kr','us','global')),
  analyst TEXT,
  published_at TIMESTAMPTZ NOT NULL,
  report_url TEXT UNIQUE,
  title TEXT,
  -- 구조화 핵심
  rating TEXT CHECK (rating IN ('strong_buy','buy','hold','sell','strong_sell')),
  rating_change TEXT CHECK (rating_change IN ('initiate','upgrade','downgrade','reiterate')),
  previous_rating TEXT,
  target_price          NUMERIC(18,4),
  previous_target_price NUMERIC(18,4),
  currency TEXT NOT NULL DEFAULT 'KRW' CHECK (currency IN ('KRW','USD')),
  upside_pct NUMERIC(8,2) GENERATED ALWAYS AS (
    CASE WHEN previous_target_price IS NOT NULL AND previous_target_price > 0
      THEN ((target_price - previous_target_price) / previous_target_price * 100)
    END
  ) STORED,
  -- 실적 전망
  forecasts JSONB NOT NULL DEFAULT '{}'::jsonb,       -- {revenue_2026e, op_profit_2026e, eps_2026e, ...}
  -- 서술
  summary TEXT,
  key_thesis TEXT,
  risks TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_analyst_code_date ON analyst_reports(code, published_at DESC);
CREATE INDEX idx_analyst_rating_change ON analyst_reports(rating_change, published_at DESC)
  WHERE rating_change IN ('upgrade','downgrade','initiate');
CREATE INDEX idx_analyst_forecasts ON analyst_reports USING GIN (forecasts);

-- 컨센서스 자동 집계 뷰 (stock_base.analyst_target_avg 대체 가능)
CREATE VIEW v_analyst_consensus AS
SELECT
  code,
  COUNT(*) FILTER (WHERE published_at > now() - interval '90 days')        AS report_count_3m,
  AVG(target_price) FILTER (WHERE published_at > now() - interval '90 days') AS avg_target_3m,
  MAX(target_price) FILTER (WHERE published_at > now() - interval '90 days') AS max_target_3m,
  MIN(target_price) FILTER (WHERE published_at > now() - interval '90 days') AS min_target_3m,
  MODE() WITHIN GROUP (ORDER BY rating)
    FILTER (WHERE published_at > now() - interval '90 days')               AS dominant_rating,
  MAX(published_at)                                                        AS latest_report_at,
  AVG(target_price) FILTER (
    WHERE published_at BETWEEN now() - interval '30 days' AND now()
  ) AS avg_target_1m,
  AVG(target_price) FILTER (
    WHERE published_at BETWEEN now() - interval '60 days' AND now() - interval '30 days'
  ) AS avg_target_prev_1m
FROM analyst_reports
GROUP BY code;


-- =====================================================================
-- D. 매매 · 포지션 (유저별 · 완전 구조화)
-- =====================================================================

-- 스타일 기본값 lookup (Claude 추천 로직이 참조)
CREATE TABLE style_defaults (
  style TEXT PRIMARY KEY,
  stop_loss_pct NUMERIC(5,2) NOT NULL,
  trailing_method TEXT NOT NULL,
  pyramiding_max_stages SMALLINT NOT NULL,
  use_time_checkpoints BOOLEAN NOT NULL,
  technical_weight NUMERIC(3,2) NOT NULL,
  thesis_weight NUMERIC(3,2) NOT NULL,
  target_horizon_days INTEGER NOT NULL,
  description TEXT
);

INSERT INTO style_defaults (style, stop_loss_pct, trailing_method, pyramiding_max_stages,
                            use_time_checkpoints, technical_weight, thesis_weight,
                            target_horizon_days, description) VALUES
  ('long-term', -10.0, 'sma60',         3, FALSE, 0.30, 0.70, 365, '중장기 홀딩, Thesis 주도'),
  ('swing',      -8.0, 'sma20',         2, FALSE, 0.50, 0.50,  21, '스윙 2~4주, 기술·Thesis 병행'),
  ('day-trade',  -5.0, 'ichimoku_base', 4, TRUE,  0.90, 0.10,   3, '기술 스윙 2~7일, 시간 청산');

-- 매매 원장 (append-only)
CREATE TABLE trades (
  id BIGSERIAL PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  code TEXT NOT NULL REFERENCES stocks(code),
  side TEXT NOT NULL CHECK (side IN ('buy','sell')),
  qty   NUMERIC(18,4) NOT NULL CHECK (qty > 0),       -- 분수주 지원 (US 소수점)
  price NUMERIC(18,4) NOT NULL CHECK (price > 0),     -- KRW 정수 + USD 소수점 공용
  executed_at TIMESTAMPTZ NOT NULL,
  trigger_note TEXT,
  realized_pnl NUMERIC(18,4),                         -- sell만 (트리거가 자동 계산)
  fees NUMERIC(18,4) NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_trades_user_code_time ON trades(user_id, code, executed_at);
CREATE INDEX idx_trades_user_time ON trades(user_id, executed_at DESC);

-- 현재 포지션 (trigger로 자동 갱신 - 수동 수정 금지)
CREATE TABLE positions (
  user_id UUID NOT NULL REFERENCES users(id),
  code TEXT NOT NULL REFERENCES stocks(code),
  qty       NUMERIC(18,4) NOT NULL DEFAULT 0,
  avg_price NUMERIC(18,4) NOT NULL DEFAULT 0,
  cost_basis NUMERIC(18,4) GENERATED ALWAYS AS (qty * avg_price) STORED,
  status TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active','Pending','Close')),
  -- 수치 파라미터 (Claude 제안 → 유저 확정)
  style TEXT REFERENCES style_defaults(style),
  stop_loss_pct NUMERIC(5,2),
  trailing_method TEXT,
  pyramiding_max_stages SMALLINT,
  use_time_checkpoints BOOLEAN DEFAULT FALSE,
  technical_weight NUMERIC(3,2),
  thesis_weight NUMERIC(3,2),
  target_horizon_days INTEGER,
  -- 태그 + 진입 맥락
  tags TEXT[] NOT NULL DEFAULT '{}',                  -- ['earnings-play','breakout','dip-buy']
  entry_context JSONB NOT NULL DEFAULT '{}'::jsonb,   -- {claude_suggestion, user_overrides, reasoning, base_grade, market_regime}
  entered_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, code)
);
CREATE INDEX idx_positions_status ON positions(user_id, status) WHERE status = 'Active';
CREATE INDEX idx_positions_tags ON positions USING GIN (tags);

-- 현금 잔고 (KRW 정수 + USD 소수점 공용)
CREATE TABLE cash_balance (
  user_id UUID NOT NULL REFERENCES users(id),
  currency TEXT NOT NULL CHECK (currency IN ('KRW','USD')),
  amount NUMERIC(18,4) NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, currency)
);

-- 감시 레벨 (position.md의 상승/하락 테이블 완전 구조화)
CREATE TABLE watch_levels (
  user_id UUID NOT NULL,
  code TEXT NOT NULL,
  level_key TEXT NOT NULL,                            -- 'target_1','target_2','target_3','trailing',
                                                      -- 'warning','base_cut','stop_loss','pyramid_1','pyramid_2'
  price           NUMERIC(18,4) NOT NULL,
  qty_to_trade    NUMERIC(18,4),
  expected_pnl    NUMERIC(18,4),
  note TEXT,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','triggered','cancelled')),
  triggered_at    TIMESTAMPTZ,
  triggered_price NUMERIC(18,4),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, code, level_key),
  FOREIGN KEY (user_id, code) REFERENCES positions(user_id, code) ON DELETE CASCADE
);
CREATE INDEX idx_watch_pending ON watch_levels(user_id, status, price) WHERE status = 'pending';

-- 포지션 서술 문서 (position.md의 진입 논리·규칙·메모)
CREATE TABLE position_docs (
  user_id UUID NOT NULL,
  code TEXT NOT NULL,
  thesis TEXT,
  action_rules TEXT,
  memo TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, code),
  FOREIGN KEY (user_id, code) REFERENCES positions(user_id, code) ON DELETE CASCADE
);


-- =====================================================================
-- E. 스냅샷 · 이벤트
-- =====================================================================

CREATE TABLE portfolio_snapshots (
  user_id UUID NOT NULL REFERENCES users(id),
  date DATE NOT NULL,
  kr_total_krw BIGINT,
  us_total_usd NUMERIC(16,2),
  krw_usd_rate NUMERIC(10,4),
  total_krw BIGINT,
  unrealized_pnl BIGINT,
  realized_pnl_daily BIGINT,
  realized_pnl_cumulative BIGINT,
  cash_krw BIGINT,
  cash_usd NUMERIC(16,2),
  weights JSONB NOT NULL DEFAULT '{}'::jsonb,
  sector_weights JSONB NOT NULL DEFAULT '{}'::jsonb,
  -- v11: 구조화 필드 (액션 플랜 자동 리마인드)
  per_stock_summary JSONB NOT NULL DEFAULT '[]'::jsonb,  -- [{code,name,close,change_pct,pnl_pct,verdict,note}]
  risk_flags        JSONB NOT NULL DEFAULT '[]'::jsonb,  -- [{type, code?, scope?, level, detail}]
  action_plan       JSONB NOT NULL DEFAULT '[]'::jsonb,  -- [{priority,code,action,qty,trigger,condition,reason,status,executed_trade_id,expires_at}]
  headline          TEXT,                                -- 한 줄 결론
  summary_content TEXT,                                  -- 자유 서술 본문 (기존)
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, date)
);
CREATE INDEX idx_portfolio_snapshots_action_status
  ON portfolio_snapshots USING GIN (action_plan jsonb_path_ops);

CREATE TABLE events (
  id BIGSERIAL PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  code TEXT REFERENCES stocks(code),
  event_type TEXT NOT NULL,                           -- 'earnings','dividend','watch_triggered','concentration_alert'
  event_date DATE,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  processed BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_events_user_unprocessed
  ON events(user_id, created_at DESC) WHERE processed = FALSE;


-- =====================================================================
-- F. 자동 재계산 함수 · 트리거
-- =====================================================================

-- positions 재계산 (이동평균 방식, NUMERIC 기반)
CREATE OR REPLACE FUNCTION recompute_position(p_user_id UUID, p_code TEXT)
RETURNS void AS $$
DECLARE
  v_qty  NUMERIC(18,4) := 0;
  v_cost NUMERIC(18,4) := 0;
  v_avg  NUMERIC(18,4) := 0;
  v_first_entry TIMESTAMPTZ;
  rec RECORD;
BEGIN
  FOR rec IN
    SELECT side, qty, price, executed_at
      FROM trades
     WHERE user_id = p_user_id AND code = p_code
     ORDER BY executed_at, id
  LOOP
    IF rec.side = 'buy' THEN
      IF v_first_entry IS NULL THEN
        v_first_entry := rec.executed_at;
      END IF;
      v_cost := v_cost + (rec.qty * rec.price);
      v_qty  := v_qty + rec.qty;
      v_avg  := CASE WHEN v_qty > 0 THEN v_cost / v_qty ELSE 0 END;
    ELSE  -- sell: 이동평균 기준 원가 차감
      v_cost := v_cost - (rec.qty * v_avg);
      v_qty  := v_qty - rec.qty;
      IF v_qty = 0 THEN
        v_cost := 0;
        v_avg  := 0;
      END IF;
    END IF;
  END LOOP;

  INSERT INTO positions (user_id, code, qty, avg_price, status, entered_at, updated_at)
  VALUES (
    p_user_id, p_code, v_qty, v_avg,
    CASE WHEN v_qty > 0 THEN 'Active' ELSE 'Close' END,
    v_first_entry, now()
  )
  ON CONFLICT (user_id, code) DO UPDATE SET
    qty = EXCLUDED.qty,
    avg_price = EXCLUDED.avg_price,
    status = EXCLUDED.status,
    updated_at = now();
END;
$$ LANGUAGE plpgsql;

-- trades INSERT 전 realized_pnl 자동 계산 (sell만)
-- ⚠️ 주의: Multi-row VALUES INSERT 시 AFTER 트리거가 statement 끝에 일괄 fire되는 PG 동작 때문에
-- 같은 statement 내 다른 row가 positions에 반영되기 전에 BEFORE 트리거가 실행됨.
-- 실 운영(매매 1건씩 INSERT)에선 문제 없으나, 대량 이관 시 반드시 row 단위로 순차 INSERT 할 것.
CREATE OR REPLACE FUNCTION compute_realized_pnl()
RETURNS TRIGGER AS $$
DECLARE
  v_current_avg NUMERIC(18,4);
BEGIN
  IF NEW.side = 'sell' AND NEW.realized_pnl IS NULL THEN
    SELECT avg_price INTO v_current_avg
      FROM positions
     WHERE user_id = NEW.user_id AND code = NEW.code;
    IF v_current_avg IS NOT NULL AND v_current_avg > 0 THEN
      NEW.realized_pnl := NEW.qty * (NEW.price - v_current_avg);
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_trades_compute_pnl
  BEFORE INSERT ON trades
  FOR EACH ROW EXECUTE FUNCTION compute_realized_pnl();

-- trades 변경 시 positions 재계산
CREATE OR REPLACE FUNCTION trg_recompute_position()
RETURNS TRIGGER AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    PERFORM recompute_position(OLD.user_id, OLD.code);
    RETURN OLD;
  ELSE
    PERFORM recompute_position(NEW.user_id, NEW.code);
    RETURN NEW;
  END IF;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_trades_recompute
  AFTER INSERT OR UPDATE OR DELETE ON trades
  FOR EACH ROW EXECUTE FUNCTION trg_recompute_position();

-- updated_at 자동 갱신 (공통 유틸)
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated        BEFORE UPDATE ON users        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_stocks_updated       BEFORE UPDATE ON stocks       FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_industries_updated   BEFORE UPDATE ON industries   FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_economy_base_updated BEFORE UPDATE ON economy_base FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_stock_base_updated   BEFORE UPDATE ON stock_base   FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_watch_updated        BEFORE UPDATE ON watch_levels FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_pos_docs_updated     BEFORE UPDATE ON position_docs FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_cash_updated         BEFORE UPDATE ON cash_balance FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- =====================================================================
-- G. Row-Level Security (SaaS 전환 시 활성화)
-- =====================================================================
-- 지금은 단일 유저라 미적용. SaaS 전환 시 아래 주석 해제.
--
-- ALTER TABLE trades            ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE positions         ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE cash_balance      ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE watch_levels      ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE position_docs     ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE stock_daily       ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE portfolio_snapshots ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE events            ENABLE ROW LEVEL SECURITY;
--
-- CREATE POLICY trades_isolation ON trades
--   USING (user_id = current_setting('app.current_user_id')::uuid);
-- -- (동일 패턴으로 나머지 테이블에 정책 생성)
--
-- 애플리케이션 시작 시 세션별로 설정:
--   SET LOCAL app.current_user_id = '<user-uuid>';
