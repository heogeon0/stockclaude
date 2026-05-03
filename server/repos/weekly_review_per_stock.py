"""weekly_review_per_stock 테이블 — 종목별 주간 회고.

라운드: 2026-05 weekly-review overhaul
per-stock-analysis 7-step 의 회고 평행. base_impact 4분류 + foregone_pnl 정량 추적.
1주 1 종목 1 row, (user_id, week_start, code) UNIQUE.
"""

from __future__ import annotations

from datetime import date as date_cls
from typing import Any

from psycopg.types.json import Jsonb

from server.config import settings
from server.db import get_conn


def upsert(
    week_start: date_cls,
    week_end: date_cls,
    code: str,
    *,
    user_id: str | None = None,
    trade_evaluations: list | None = None,
    base_snapshot: dict | None = None,
    base_impact: str | None = None,
    base_thesis_aligned: bool | None = None,
    base_refresh_required: bool | None = None,
    base_refreshed_during_review: bool | None = None,
    base_appendback_done: bool | None = None,
    base_narrative_revision_proposed: bool | None = None,
    content: str | None = None,
) -> None:
    """upsert — 같은 (user_id, week_start, code) 덮어쓰기.

    None 인 인자는 기존 값 유지 (COALESCE).
    """
    uid = user_id or settings.stock_user_id
    if base_impact is not None and base_impact not in (
        "decisive", "supportive", "contradictory", "neutral",
    ):
        raise ValueError(f"invalid base_impact: {base_impact}")

    te_j = Jsonb(trade_evaluations) if trade_evaluations is not None else None
    bs_j = Jsonb(base_snapshot) if base_snapshot is not None else None

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO weekly_review_per_stock (
              user_id, week_start, week_end, code,
              trade_evaluations, base_snapshot, base_impact,
              base_thesis_aligned, base_refresh_required,
              base_refreshed_during_review, base_appendback_done,
              base_narrative_revision_proposed, content
            ) VALUES (%s, %s, %s, %s,
                      COALESCE(%s, '[]'::jsonb), %s, %s,
                      %s, COALESCE(%s, FALSE),
                      COALESCE(%s, FALSE), COALESCE(%s, FALSE),
                      COALESCE(%s, FALSE), %s)
            ON CONFLICT (user_id, week_start, code) DO UPDATE SET
              week_end                          = EXCLUDED.week_end,
              trade_evaluations                 = COALESCE(EXCLUDED.trade_evaluations, weekly_review_per_stock.trade_evaluations),
              base_snapshot                     = COALESCE(EXCLUDED.base_snapshot, weekly_review_per_stock.base_snapshot),
              base_impact                       = COALESCE(EXCLUDED.base_impact, weekly_review_per_stock.base_impact),
              base_thesis_aligned               = COALESCE(EXCLUDED.base_thesis_aligned, weekly_review_per_stock.base_thesis_aligned),
              base_refresh_required             = COALESCE(EXCLUDED.base_refresh_required, weekly_review_per_stock.base_refresh_required),
              base_refreshed_during_review      = COALESCE(EXCLUDED.base_refreshed_during_review, weekly_review_per_stock.base_refreshed_during_review),
              base_appendback_done              = COALESCE(EXCLUDED.base_appendback_done, weekly_review_per_stock.base_appendback_done),
              base_narrative_revision_proposed  = COALESCE(EXCLUDED.base_narrative_revision_proposed, weekly_review_per_stock.base_narrative_revision_proposed),
              content                           = COALESCE(EXCLUDED.content, weekly_review_per_stock.content)
            """,
            (
                uid, week_start, week_end, code,
                te_j, bs_j, base_impact,
                base_thesis_aligned, base_refresh_required,
                base_refreshed_during_review, base_appendback_done,
                base_narrative_revision_proposed, content,
            ),
        )


def get(week_start: date_cls, code: str, user_id: str | None = None) -> dict[str, Any] | None:
    uid = user_id or settings.stock_user_id
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT * FROM weekly_review_per_stock
             WHERE user_id = %s AND week_start = %s AND code = %s
            """,
            (uid, week_start, code),
        )
        return cur.fetchone()


def list_by_week(week_start: date_cls, user_id: str | None = None) -> list[dict[str, Any]]:
    """Phase 2 인풋 join 용 — 한 주의 모든 종목 회고."""
    uid = user_id or settings.stock_user_id
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT wrps.*, s.name AS stock_name, s.market
              FROM weekly_review_per_stock wrps
              JOIN stocks s USING(code)
             WHERE wrps.user_id = %s AND wrps.week_start = %s
             ORDER BY s.market, wrps.code
            """,
            (uid, week_start),
        )
        return cur.fetchall()


def list_by_code(
    code: str,
    weeks: int = 12,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    """종목별 회고 시계열 — 장기 thesis 추적용."""
    uid = user_id or settings.stock_user_id
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT week_start, week_end, base_impact, base_thesis_aligned,
                   trade_evaluations, content
              FROM weekly_review_per_stock
             WHERE user_id = %s AND code = %s
             ORDER BY week_start DESC LIMIT %s
            """,
            (uid, code, weeks),
        )
        return cur.fetchall()
