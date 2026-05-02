-- 13_alter_base_phase_momentum.sql
-- v4 (2026-05): base inline 절차 깊이 강화에 따른 메타 컬럼 추가.
-- - economy_base: cycle_phase (확장/정점/수축/저점) + scenario_probs (jsonb {bull/base/bear})
-- - industries: cycle_phase (도입/성장/성숙/쇠퇴) + momentum_rs_3m/6m + leader_followers (jsonb)
-- 기존 row 의 새 컬럼은 NULL 유지 — 다음 base 갱신 시 자동 채움.

-- economy_base
ALTER TABLE economy_base
  ADD COLUMN IF NOT EXISTS cycle_phase TEXT;

ALTER TABLE economy_base
  ADD COLUMN IF NOT EXISTS scenario_probs JSONB;

-- CHECK 제약 (idempotent): 기존 제약 drop 후 재생성
ALTER TABLE economy_base
  DROP CONSTRAINT IF EXISTS economy_base_cycle_phase_check;

ALTER TABLE economy_base
  ADD CONSTRAINT economy_base_cycle_phase_check
  CHECK (cycle_phase IN ('확장','정점','수축','저점') OR cycle_phase IS NULL);

-- industries
ALTER TABLE industries
  ADD COLUMN IF NOT EXISTS cycle_phase TEXT;

ALTER TABLE industries
  ADD COLUMN IF NOT EXISTS momentum_rs_3m NUMERIC;

ALTER TABLE industries
  ADD COLUMN IF NOT EXISTS momentum_rs_6m NUMERIC;

ALTER TABLE industries
  ADD COLUMN IF NOT EXISTS leader_followers JSONB;

ALTER TABLE industries
  DROP CONSTRAINT IF EXISTS industries_cycle_phase_check;

ALTER TABLE industries
  ADD CONSTRAINT industries_cycle_phase_check
  CHECK (cycle_phase IN ('도입','성장','성숙','쇠퇴') OR cycle_phase IS NULL);
