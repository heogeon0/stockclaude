"""weekly_reviews 테이블 — 주간 회고/학습 derived data."""

from __future__ import annotations

from datetime import date as date_cls
from decimal import Decimal
from typing import Any

from psycopg.types.json import Jsonb

from server.config import settings
from server.db import get_conn


def get_review(week_start: date_cls, user_id: str | None = None) -> dict[str, Any] | None:
    uid = user_id or settings.stock_user_id
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT id, user_id, week_start, week_end,
                   realized_pnl_kr, realized_pnl_us,
                   unrealized_pnl_kr, unrealized_pnl_us,
                   trade_count,
                   win_rate, rule_evaluations, highlights, next_week_actions,
                   rule_win_rates, pattern_findings, lessons_learned,
                   next_week_emphasize, next_week_avoid, override_freq_30d,
                   base_phase0_log, phase3_log, per_stock_review_count,
                   base_appendback_count, propose_narrative_revision_count,
                   headline, content, created_at, updated_at
              FROM weekly_reviews
             WHERE user_id = %s AND week_start = %s
            """,
            (uid, week_start),
        )
        return cur.fetchone()


def list_reviews(limit: int = 12, user_id: str | None = None) -> list[dict[str, Any]]:
    uid = user_id or settings.stock_user_id
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT id, week_start, week_end, trade_count,
                   realized_pnl_kr, realized_pnl_us,
                   unrealized_pnl_kr, unrealized_pnl_us,
                   headline, created_at
              FROM weekly_reviews
             WHERE user_id = %s
             ORDER BY week_start DESC
             LIMIT %s
            """,
            (uid, limit),
        )
        return cur.fetchall()


def upsert_review(
    week_start: date_cls,
    week_end: date_cls,
    *,
    user_id: str | None = None,
    realized_pnl_kr: Decimal | None = None,
    realized_pnl_us: Decimal | None = None,
    unrealized_pnl_kr: Decimal | None = None,
    unrealized_pnl_us: Decimal | None = None,
    trade_count: int | None = None,
    win_rate: dict | None = None,
    rule_evaluations: list | None = None,
    highlights: list | None = None,
    next_week_actions: list | None = None,
    headline: str | None = None,
    content: str | None = None,
    # v7 (2026-05): 결론 정량 컬럼
    rule_win_rates: dict | None = None,
    pattern_findings: list | None = None,
    lessons_learned: list | None = None,
    next_week_emphasize: list | None = None,
    next_week_avoid: list | None = None,
    override_freq_30d: dict | None = None,
    # 라운드 2026-05 weekly-review overhaul: 4-Phase 결과 영속
    base_phase0_log: dict | None = None,
    phase3_log: dict | None = None,
    per_stock_review_count: int | None = None,
    base_appendback_count: int | None = None,
    propose_narrative_revision_count: int | None = None,
) -> None:
    uid = user_id or settings.stock_user_id

    # NOT NULL JSONB 필드는 None 이면 빈 컨테이너로 (기존 값 유지 위해 COALESCE)
    win_rate_j = Jsonb(win_rate) if win_rate is not None else None
    rule_eval_j = Jsonb(rule_evaluations) if rule_evaluations is not None else None
    highlights_j = Jsonb(highlights) if highlights is not None else None
    actions_j = Jsonb(next_week_actions) if next_week_actions is not None else None
    # v7 정량 컬럼 (NULL 허용, 기존 값 유지)
    rwr_j = Jsonb(rule_win_rates) if rule_win_rates is not None else None
    pf_j = Jsonb(pattern_findings) if pattern_findings is not None else None
    ll_j = Jsonb(lessons_learned) if lessons_learned is not None else None
    nwe_j = Jsonb(next_week_emphasize) if next_week_emphasize is not None else None
    nwa_j = Jsonb(next_week_avoid) if next_week_avoid is not None else None
    of_j = Jsonb(override_freq_30d) if override_freq_30d is not None else None
    # 4-Phase JSONB
    p0_j = Jsonb(base_phase0_log) if base_phase0_log is not None else None
    p3_j = Jsonb(phase3_log) if phase3_log is not None else None

    # NOT NULL 컬럼 (trade_count) 안전장치: 신규 INSERT 인 경우 0 디폴트.
    # ON CONFLICT 발생 시 COALESCE 로 기존 값 보존.
    trade_count_insert = trade_count if trade_count is not None else 0

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO weekly_reviews (
                user_id, week_start, week_end,
                realized_pnl_kr, realized_pnl_us,
                unrealized_pnl_kr, unrealized_pnl_us,
                trade_count,
                win_rate, rule_evaluations, highlights, next_week_actions,
                headline, content,
                rule_win_rates, pattern_findings, lessons_learned,
                next_week_emphasize, next_week_avoid, override_freq_30d,
                base_phase0_log, phase3_log,
                per_stock_review_count, base_appendback_count,
                propose_narrative_revision_count
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                      COALESCE(%s, '{}'::jsonb),
                      COALESCE(%s, '[]'::jsonb),
                      COALESCE(%s, '[]'::jsonb),
                      COALESCE(%s, '[]'::jsonb),
                      %s, %s,
                      %s, %s, %s, %s, %s, %s,
                      %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, week_start) DO UPDATE SET
              week_end          = EXCLUDED.week_end,
              realized_pnl_kr   = COALESCE(EXCLUDED.realized_pnl_kr, weekly_reviews.realized_pnl_kr),
              realized_pnl_us   = COALESCE(EXCLUDED.realized_pnl_us, weekly_reviews.realized_pnl_us),
              unrealized_pnl_kr = COALESCE(EXCLUDED.unrealized_pnl_kr, weekly_reviews.unrealized_pnl_kr),
              unrealized_pnl_us = COALESCE(EXCLUDED.unrealized_pnl_us, weekly_reviews.unrealized_pnl_us),
              -- trade_count: 0 은 INSERT 안전장치 sentinel — 명시 갱신만 반영하기 위해 별도 case
              trade_count       = CASE
                                    WHEN %s::int IS NOT NULL THEN EXCLUDED.trade_count
                                    ELSE weekly_reviews.trade_count
                                  END,
              win_rate          = COALESCE(EXCLUDED.win_rate, weekly_reviews.win_rate),
              rule_evaluations  = COALESCE(EXCLUDED.rule_evaluations, weekly_reviews.rule_evaluations),
              highlights        = COALESCE(EXCLUDED.highlights, weekly_reviews.highlights),
              next_week_actions = COALESCE(EXCLUDED.next_week_actions, weekly_reviews.next_week_actions),
              headline          = COALESCE(EXCLUDED.headline, weekly_reviews.headline),
              content           = COALESCE(EXCLUDED.content, weekly_reviews.content),
              rule_win_rates    = COALESCE(EXCLUDED.rule_win_rates, weekly_reviews.rule_win_rates),
              pattern_findings  = COALESCE(EXCLUDED.pattern_findings, weekly_reviews.pattern_findings),
              lessons_learned   = COALESCE(EXCLUDED.lessons_learned, weekly_reviews.lessons_learned),
              next_week_emphasize = COALESCE(EXCLUDED.next_week_emphasize, weekly_reviews.next_week_emphasize),
              next_week_avoid   = COALESCE(EXCLUDED.next_week_avoid, weekly_reviews.next_week_avoid),
              override_freq_30d = COALESCE(EXCLUDED.override_freq_30d, weekly_reviews.override_freq_30d),
              base_phase0_log   = COALESCE(EXCLUDED.base_phase0_log, weekly_reviews.base_phase0_log),
              phase3_log        = COALESCE(EXCLUDED.phase3_log, weekly_reviews.phase3_log),
              per_stock_review_count = COALESCE(EXCLUDED.per_stock_review_count, weekly_reviews.per_stock_review_count),
              base_appendback_count  = COALESCE(EXCLUDED.base_appendback_count, weekly_reviews.base_appendback_count),
              propose_narrative_revision_count = COALESCE(EXCLUDED.propose_narrative_revision_count, weekly_reviews.propose_narrative_revision_count),
              updated_at        = now()
            """,
            (
                uid, week_start, week_end,
                realized_pnl_kr, realized_pnl_us,
                unrealized_pnl_kr, unrealized_pnl_us,
                trade_count_insert,
                win_rate_j, rule_eval_j, highlights_j, actions_j,
                headline, content,
                rwr_j, pf_j, ll_j, nwe_j, nwa_j, of_j,
                p0_j, p3_j,
                per_stock_review_count, base_appendback_count,
                propose_narrative_revision_count,
                trade_count,  # CASE WHEN 의 sentinel 비교용 (원본 None/Int)
            ),
        )
