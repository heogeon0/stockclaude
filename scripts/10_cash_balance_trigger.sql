-- 10_cash_balance_trigger.sql
-- record_trade 시 cash_balance 자동 갱신 (issue #7)
-- 변경 후엔 trades INSERT → 통화별 cash_balance.amount 자동 가감.
--   buy:  cash -= qty * price + fees
--   sell: cash += qty * price - fees
-- 통화는 stocks.currency 에서 결정 (trades 자체엔 currency 없음).

CREATE OR REPLACE FUNCTION update_cash_balance_on_trade() RETURNS TRIGGER AS $$
DECLARE
    trade_currency TEXT;
    cash_change NUMERIC(18, 4);
BEGIN
    -- 통화 결정 (stocks.currency)
    SELECT currency INTO trade_currency FROM stocks WHERE code = NEW.code;
    IF trade_currency IS NULL THEN
        RAISE EXCEPTION 'Stock % has no currency', NEW.code;
    END IF;

    -- 변동량 계산
    IF NEW.side = 'sell' THEN
        cash_change := NEW.qty * NEW.price - COALESCE(NEW.fees, 0);
    ELSE  -- 'buy'
        cash_change := -(NEW.qty * NEW.price + COALESCE(NEW.fees, 0));
    END IF;

    -- cash_balance UPSERT
    INSERT INTO cash_balance (user_id, currency, amount, updated_at)
    VALUES (NEW.user_id, trade_currency, cash_change, NOW())
    ON CONFLICT (user_id, currency)
    DO UPDATE SET
        amount = cash_balance.amount + cash_change,
        updated_at = NOW();

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trades_update_cash_balance ON trades;
CREATE TRIGGER trades_update_cash_balance
AFTER INSERT ON trades
FOR EACH ROW EXECUTE FUNCTION update_cash_balance_on_trade();

-- 검증 쿼리 (수동 실행)
-- INSERT INTO trades (...) VALUES (...) 후
-- SELECT * FROM cash_balance WHERE user_id = '...';
