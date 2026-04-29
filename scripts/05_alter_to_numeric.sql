-- =====================================================================
-- Phase 2a: BIGINT → NUMERIC(18,4) 마이그레이션
-- =====================================================================
-- 이유: US 분수주 (NVDA 26.797주) + 소수점 가격 ($195.5188) 저장 위함
-- 영향: qty, price, avg_price, cost_basis, realized_pnl, fees,
--       fair_value_*, analyst_target_*, eps, bps, cash amount,
--       watch_levels.price/expected_pnl, stock_daily OHLCV + SMA/BB,
--       analyst_reports.target_price
--
-- market_cap, volume, portfolio_snapshots KRW 합계는 BIGINT 유지
-- (큰 정수로 표현하는 게 더 자연스럽고 분수 필요 없음)
--
-- 주의: GENERATED 컬럼 DROP → 재생성 필요 (트리거 함수 내부 변수 타입도 교체)
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- 1) 의존 트리거·함수 DROP (재생성할 것)
-- ---------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_trades_compute_pnl ON trades;
DROP TRIGGER IF EXISTS trg_trades_recompute ON trades;
DROP FUNCTION IF EXISTS compute_realized_pnl() CASCADE;
DROP FUNCTION IF EXISTS trg_recompute_position() CASCADE;
DROP FUNCTION IF EXISTS recompute_position(UUID, TEXT) CASCADE;

-- ---------------------------------------------------------------------
-- 2) GENERATED 컬럼 DROP (type change 위해)
-- ---------------------------------------------------------------------
ALTER TABLE positions        DROP COLUMN cost_basis;
ALTER TABLE analyst_reports  DROP COLUMN upside_pct;

-- ---------------------------------------------------------------------
-- 3) trades — qty·price·realized_pnl·fees
-- ---------------------------------------------------------------------
ALTER TABLE trades
  ALTER COLUMN qty          TYPE NUMERIC(18,4) USING qty::NUMERIC,
  ALTER COLUMN price        TYPE NUMERIC(18,4) USING price::NUMERIC,
  ALTER COLUMN realized_pnl TYPE NUMERIC(18,4) USING realized_pnl::NUMERIC,
  ALTER COLUMN fees         TYPE NUMERIC(18,4) USING fees::NUMERIC;

-- CHECK 제약 qty > 0 유지 (NUMERIC에서도 작동)

-- ---------------------------------------------------------------------
-- 4) positions — qty·avg_price + cost_basis 재생성
-- ---------------------------------------------------------------------
ALTER TABLE positions
  ALTER COLUMN qty       TYPE NUMERIC(18,4) USING qty::NUMERIC,
  ALTER COLUMN avg_price TYPE NUMERIC(18,4) USING avg_price::NUMERIC;

ALTER TABLE positions
  ADD COLUMN cost_basis NUMERIC(18,4) GENERATED ALWAYS AS (qty * avg_price) STORED;

-- ---------------------------------------------------------------------
-- 5) cash_balance
-- ---------------------------------------------------------------------
ALTER TABLE cash_balance
  ALTER COLUMN amount TYPE NUMERIC(18,4) USING amount::NUMERIC;

-- ---------------------------------------------------------------------
-- 6) watch_levels
-- ---------------------------------------------------------------------
ALTER TABLE watch_levels
  ALTER COLUMN price           TYPE NUMERIC(18,4) USING price::NUMERIC,
  ALTER COLUMN qty_to_trade    TYPE NUMERIC(18,4) USING qty_to_trade::NUMERIC,
  ALTER COLUMN expected_pnl    TYPE NUMERIC(18,4) USING expected_pnl::NUMERIC,
  ALTER COLUMN triggered_price TYPE NUMERIC(18,4) USING triggered_price::NUMERIC;

-- ---------------------------------------------------------------------
-- 7) stock_base — valuation/target/eps/bps
-- ---------------------------------------------------------------------
ALTER TABLE stock_base
  ALTER COLUMN fair_value_min     TYPE NUMERIC(18,4) USING fair_value_min::NUMERIC,
  ALTER COLUMN fair_value_avg     TYPE NUMERIC(18,4) USING fair_value_avg::NUMERIC,
  ALTER COLUMN fair_value_max     TYPE NUMERIC(18,4) USING fair_value_max::NUMERIC,
  ALTER COLUMN analyst_target_avg TYPE NUMERIC(18,4) USING analyst_target_avg::NUMERIC,
  ALTER COLUMN analyst_target_max TYPE NUMERIC(18,4) USING analyst_target_max::NUMERIC,
  ALTER COLUMN eps                TYPE NUMERIC(18,4) USING eps::NUMERIC,
  ALTER COLUMN bps                TYPE NUMERIC(18,4) USING bps::NUMERIC;
-- market_cap 은 BIGINT 유지 (분수 불필요, 큰 원/달러 금액)

-- ---------------------------------------------------------------------
-- 8) stock_daily — OHLC + SMA/BB (volume은 BIGINT 유지)
-- ---------------------------------------------------------------------
ALTER TABLE stock_daily
  ALTER COLUMN open      TYPE NUMERIC(18,4) USING open::NUMERIC,
  ALTER COLUMN high      TYPE NUMERIC(18,4) USING high::NUMERIC,
  ALTER COLUMN low       TYPE NUMERIC(18,4) USING low::NUMERIC,
  ALTER COLUMN close     TYPE NUMERIC(18,4) USING close::NUMERIC,
  ALTER COLUMN bb_upper  TYPE NUMERIC(18,4) USING bb_upper::NUMERIC,
  ALTER COLUMN bb_middle TYPE NUMERIC(18,4) USING bb_middle::NUMERIC,
  ALTER COLUMN bb_lower  TYPE NUMERIC(18,4) USING bb_lower::NUMERIC,
  ALTER COLUMN sma5      TYPE NUMERIC(18,4) USING sma5::NUMERIC,
  ALTER COLUMN sma20     TYPE NUMERIC(18,4) USING sma20::NUMERIC,
  ALTER COLUMN sma60     TYPE NUMERIC(18,4) USING sma60::NUMERIC,
  ALTER COLUMN sma120    TYPE NUMERIC(18,4) USING sma120::NUMERIC,
  ALTER COLUMN sma200    TYPE NUMERIC(18,4) USING sma200::NUMERIC;

-- ---------------------------------------------------------------------
-- 9) analyst_reports + upside_pct 재생성 (뷰 의존성 처리)
-- ---------------------------------------------------------------------
DROP VIEW IF EXISTS v_analyst_consensus;

ALTER TABLE analyst_reports
  ALTER COLUMN target_price          TYPE NUMERIC(18,4) USING target_price::NUMERIC,
  ALTER COLUMN previous_target_price TYPE NUMERIC(18,4) USING previous_target_price::NUMERIC;

ALTER TABLE analyst_reports
  ADD COLUMN upside_pct NUMERIC(8,2) GENERATED ALWAYS AS (
    CASE WHEN previous_target_price IS NOT NULL AND previous_target_price > 0
      THEN ((target_price - previous_target_price) / previous_target_price * 100)
    END
  ) STORED;

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

-- ---------------------------------------------------------------------
-- 10) 트리거 함수 재생성 (NUMERIC 기반)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION recompute_position(p_user_id UUID, p_code TEXT)
RETURNS void AS $$
DECLARE
  v_qty   NUMERIC(18,4) := 0;
  v_cost  NUMERIC(18,4) := 0;
  v_avg   NUMERIC(18,4) := 0;
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
    qty       = EXCLUDED.qty,
    avg_price = EXCLUDED.avg_price,
    status    = EXCLUDED.status,
    updated_at = now();
END;
$$ LANGUAGE plpgsql;

-- ⚠️ Multi-row VALUES INSERT 시 AFTER 트리거가 statement 끝에 일괄 fire되는 PG 동작 때문에
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

COMMIT;

-- =====================================================================
-- 검증
-- =====================================================================
-- SELECT column_name, data_type, numeric_precision, numeric_scale
--   FROM information_schema.columns
--  WHERE table_name IN ('trades','positions','stock_base','stock_daily','cash_balance','watch_levels','analyst_reports')
--    AND data_type = 'numeric'
--  ORDER BY table_name, column_name;
