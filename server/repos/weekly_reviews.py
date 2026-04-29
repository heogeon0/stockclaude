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
) -> None:
    uid = user_id or settings.stock_user_id

    # NOT NULL JSONB 필드는 None 이면 빈 컨테이너로 (기존 값 유지 위해 COALESCE)
    win_rate_j = Jsonb(win_rate) if win_rate is not None else None
    rule_eval_j = Jsonb(rule_evaluations) if rule_evaluations is not None else None
    highlights_j = Jsonb(highlights) if highlights is not None else None
    actions_j = Jsonb(next_week_actions) if next_week_actions is not None else None

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO weekly_reviews (
                user_id, week_start, week_end,
                realized_pnl_kr, realized_pnl_us,
                unrealized_pnl_kr, unrealized_pnl_us,
                trade_count,
                win_rate, rule_evaluations, highlights, next_week_actions,
                headline, content
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                      COALESCE(%s, '{}'::jsonb),
                      COALESCE(%s, '[]'::jsonb),
                      COALESCE(%s, '[]'::jsonb),
                      COALESCE(%s, '[]'::jsonb),
                      %s, %s)
            ON CONFLICT (user_id, week_start) DO UPDATE SET
              week_end          = EXCLUDED.week_end,
              realized_pnl_kr   = COALESCE(EXCLUDED.realized_pnl_kr, weekly_reviews.realized_pnl_kr),
              realized_pnl_us   = COALESCE(EXCLUDED.realized_pnl_us, weekly_reviews.realized_pnl_us),
              unrealized_pnl_kr = COALESCE(EXCLUDED.unrealized_pnl_kr, weekly_reviews.unrealized_pnl_kr),
              unrealized_pnl_us = COALESCE(EXCLUDED.unrealized_pnl_us, weekly_reviews.unrealized_pnl_us),
              trade_count       = COALESCE(EXCLUDED.trade_count, weekly_reviews.trade_count),
              win_rate          = COALESCE(EXCLUDED.win_rate, weekly_reviews.win_rate),
              rule_evaluations  = COALESCE(EXCLUDED.rule_evaluations, weekly_reviews.rule_evaluations),
              highlights        = COALESCE(EXCLUDED.highlights, weekly_reviews.highlights),
              next_week_actions = COALESCE(EXCLUDED.next_week_actions, weekly_reviews.next_week_actions),
              headline          = COALESCE(EXCLUDED.headline, weekly_reviews.headline),
              content           = COALESCE(EXCLUDED.content, weekly_reviews.content),
              updated_at        = now()
            """,
            (
                uid, week_start, week_end,
                realized_pnl_kr, realized_pnl_us,
                unrealized_pnl_kr, unrealized_pnl_us,
                trade_count,
                win_rate_j, rule_eval_j, highlights_j, actions_j,
                headline, content,
            ),
        )
