-- 18_alter_weekly_reviews_phase_logs.sql
-- 라운드: 2026-05 weekly-review overhaul
-- weekly_reviews 에 4-Phase 결과 영속 컬럼 5개 추가.
-- Phase 0 (base 갱신) / Phase 3 (append-back) 로그 + 종목별 회고 카운트.
-- ====================================================================

ALTER TABLE weekly_reviews
  ADD COLUMN IF NOT EXISTS base_phase0_log JSONB;
  -- {economy: {kr_refreshed_at, us_refreshed_at},
  --  industries: [{code, refreshed_at}],
  --  stocks:     [{code, refreshed_at}],
  --  skipped:    [{target_type, target_key, reason}]}

ALTER TABLE weekly_reviews
  ADD COLUMN IF NOT EXISTS phase3_log JSONB;
  -- {appended_facts: [{target_type, target_key, fact_text, appended_at}],
  --  proposed_revisions: [{target_type, target_key, divergence_summary,
  --                        evidence_trades, status='pending_user_review'}]}

ALTER TABLE weekly_reviews
  ADD COLUMN IF NOT EXISTS per_stock_review_count INT;
  -- weekly_review_per_stock row 수 (Phase 1 결과)

ALTER TABLE weekly_reviews
  ADD COLUMN IF NOT EXISTS base_appendback_count INT;
  -- Phase 3 자동 append 건수

ALTER TABLE weekly_reviews
  ADD COLUMN IF NOT EXISTS propose_narrative_revision_count INT;
  -- Phase 3 사용자 큐 적재 건수
