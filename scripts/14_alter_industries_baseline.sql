-- 14_alter_industries_baseline.sql
-- v6 (2026-05): industries 테이블에 산업 표준 메트릭 컬럼 추가.
-- 종목 financial_grade (A/B/C/D) 결정 시 절대값 anchor 금지, 산업 평균 대비 본문 판단의 근거.
-- per-stock-analysis 의 6단계 LLM 판단에서 인용.

ALTER TABLE industries
  ADD COLUMN IF NOT EXISTS avg_per NUMERIC;

ALTER TABLE industries
  ADD COLUMN IF NOT EXISTS avg_pbr NUMERIC;

ALTER TABLE industries
  ADD COLUMN IF NOT EXISTS avg_roe NUMERIC;

ALTER TABLE industries
  ADD COLUMN IF NOT EXISTS avg_op_margin NUMERIC;

ALTER TABLE industries
  ADD COLUMN IF NOT EXISTS vol_baseline_30d NUMERIC;

-- 백필: NULL 유지. 다음 base-industry 갱신 (inline 절차 v4-c~e + v6-j) 시 자동 채움.
