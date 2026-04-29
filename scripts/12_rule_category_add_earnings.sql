-- 12_rule_category_add_earnings.sql
-- 룰 카탈로그 확장 — `실적D-1선제진입` 추가 (15번째 룰).
-- 의미: 실적 발표 D-1/D-2 시점 강매수 시그널 + 컨센 강세 시 선제 매수 (양면 베팅의 buy 측면).
-- 사용자 4/22 SK하이닉스 case (id 17) 매핑 + 향후 비슷한 패턴 추적.

ALTER TABLE trades
  DROP CONSTRAINT IF EXISTS trades_rule_category_check;

ALTER TABLE trades
  ADD CONSTRAINT trades_rule_category_check
  CHECK (rule_category IS NULL OR rule_category IN (
    -- 진입 (6 — 신규 추가)
    '강매수시그널진입',
    '신고가돌파매수',
    '가치신규진입',
    'VCP_SEPA진입',
    '피라미딩D1안착',
    '실적D-1선제진입',  -- ⭐ NEW
    -- 청산 (6)
    '1차목표도달익절',
    '이벤트익절',
    '모멘텀꼴찌청산',
    '피라미딩실패컷',
    'RSI과열청산',
    'Defensive조기익절',
    -- 관리 (3)
    '집중도25%회수',
    'ATR손절',
    '컨센하향청산'
  ));

-- id 17 매핑 (4/22 SK하이닉스 +1주 — 실적 D-1 선제)
UPDATE trades SET rule_category = '실적D-1선제진입' WHERE id = 17;
