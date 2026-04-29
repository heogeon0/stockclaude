-- 11_trades_rule_category.sql
-- trades.rule_category 컬럼 추가 — 매매 시 적용 룰 enum 명시.
-- weekly_reviews.win_rate jsonb 키와 정합 (한글 룰명).
-- references/rule-catalog.md 의 14 룰 + NULL (옛 trades / 명시 안 한 매매).

ALTER TABLE trades
  ADD COLUMN IF NOT EXISTS rule_category TEXT;

-- CHECK constraint — 카탈로그 14 룰 + NULL 허용
ALTER TABLE trades
  DROP CONSTRAINT IF EXISTS trades_rule_category_check;

ALTER TABLE trades
  ADD CONSTRAINT trades_rule_category_check
  CHECK (rule_category IS NULL OR rule_category IN (
    -- 진입
    '강매수시그널진입',
    '신고가돌파매수',
    '가치신규진입',
    'VCP_SEPA진입',
    '피라미딩D1안착',
    -- 청산
    '1차목표도달익절',
    '이벤트익절',
    '모멘텀꼴찌청산',
    '피라미딩실패컷',
    'RSI과열청산',
    'Defensive조기익절',
    -- 관리
    '집중도25%회수',
    'ATR손절',
    '컨센하향청산'
  ));

-- 인덱스 — 룰별 조회 (list_trades_by_rule 등) 빠르게
CREATE INDEX IF NOT EXISTS idx_trades_rule_category
  ON trades(rule_category)
  WHERE rule_category IS NOT NULL;

-- 오타 정정 — weekly_reviews 의 '모멘텀꽜재청산' → '모멘텀꼴찌청산'
UPDATE weekly_reviews
SET win_rate = (
  win_rate - '모멘텀꽜재청산'
  || jsonb_build_object('모멘텀꼴찌청산', win_rate->'모멘텀꽜재청산')
)
WHERE win_rate ? '모멘텀꽜재청산';
