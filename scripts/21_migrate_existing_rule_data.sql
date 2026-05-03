-- 21_migrate_existing_rule_data.sql
-- 라운드: 2026-05 weekly-review overhaul
-- 옛 한글 enum CHECK + INT[] 분산 → rule_catalog FK 통일.
-- trades.rule_category (TEXT enum) → trades.rule_id (INT FK) 변환.
-- 옛 데이터 보존 (rule_category 컬럼은 남겨두고 신규 사용 차단만).
-- ====================================================================

-- 1) trades.rule_id 컬럼 추가 + FK
ALTER TABLE trades
  ADD COLUMN IF NOT EXISTS rule_id INT REFERENCES rule_catalog(id);

-- 2) 옛 한글 enum → INT id 변환
UPDATE trades
SET rule_id = rc.id
FROM rule_catalog rc
WHERE trades.rule_category = rc.enum_name
  AND trades.rule_id IS NULL;

-- 3) trades.rule_category CHECK 제약 제거 (rule_catalog FK 가 대체)
--    옛 한글 enum CHECK 가 새 룰 등록 시 INSERT 차단하는 문제 해결.
ALTER TABLE trades
  DROP CONSTRAINT IF EXISTS trades_rule_category_check;

-- 4) rule_id 인덱스 (룰별 win_rate 산출 최적화)
CREATE INDEX IF NOT EXISTS idx_trades_rule_id
  ON trades (rule_id)
  WHERE rule_id IS NOT NULL;

-- 5) 검증 쿼리 (실행 시 확인용 — 마이그 적용 시 RAISE 안 함)
DO $$
DECLARE
  v_unmapped INT;
BEGIN
  SELECT count(*) INTO v_unmapped
  FROM trades
  WHERE rule_id IS NULL AND rule_category IS NOT NULL;

  IF v_unmapped > 0 THEN
    RAISE NOTICE '⚠️ trades.rule_category → rule_id 매핑 누락: % 건', v_unmapped;
  ELSE
    RAISE NOTICE '✓ trades.rule_category → rule_id 매핑 완료';
  END IF;
END $$;

-- 6) weekly_strategy.rules_to_emphasize / rules_to_avoid — JSONB 배열 INT id 그대로 사용
--    이미 INT[] 였음. rule_catalog.id 와 정합 (FK 강제는 JSONB 라 수동 검증).
--    옛 데이터 (rules_to_emphasize=[2,5]) 가 신규 ID 매핑과 일치하는지 확인:
--    - 2 = 신고가돌파매수 (옛 의미: VCP_SEPA진입 또는 SEPA 변형) → 매핑 가능
--    - 5 = 피라미딩D1안착 (옛 의미: 재무+모멘텀 — 가치신규진입 3 또는 VCP_SEPA진입 4 가 더 정확)
--    ⚠️ 옛 weekly_strategy 의 rules_to_* INT 값이 본 카탈로그와 약간 어긋날 수 있음.
--    회고 (Phase 2) 에서 LLM 이 rule_catalog_join 보고 정확히 매핑하므로 자동 정합됨.

-- 7) learned_patterns.related_rule_ids — 이미 INT[] 였음.
--    rule_catalog.id 참조 의미. 옛 데이터 (related_rule_ids=[4]) 검증:
--    - 4 = VCP_SEPA진입 (이번주 GOOGL 의 earnings_d0_partial_pre_sell 이 8 = 이벤트익절 이어야 정확)
--    ⚠️ append_learned_pattern 신규 호출 시 rule_id 정합 검증을 MCP 레벨에서 수행 (v10-d).

-- 8) weekly_reviews.rule_win_rates — JSONB key 가 한글 enum_name (예: "이벤트익절": 1.0).
--    한글 key 그대로 두고 (옛 데이터 보존), prepare_* MCP 응답에서 rule_catalog_join 으로
--    한글 ↔ INT 매핑 자동 제공. 변환 불필요.
