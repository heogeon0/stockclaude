"""economy_base, economy_daily 테이블."""

from __future__ import annotations

from datetime import date as date_cls
from decimal import Decimal
from typing import Any

from psycopg.types.json import Jsonb

from server.db import get_conn


def get_base(market: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT market, context, content, updated_at, expires_at FROM economy_base WHERE market = %s",
            (market,),
        )
        return cur.fetchone()


def upsert_base(
    market: str,
    *,
    context: dict | None = None,
    content: str | None = None,
) -> None:
    # context NOT NULL 제약 대응: None이면 기존 값 유지 (없으면 {})
    if context is None:
        existing = get_base(market)
        context = (existing.get("context") if existing else None) or {}

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO economy_base (market, context, content) VALUES (%s, %s, %s)
            ON CONFLICT (market) DO UPDATE SET
              context = COALESCE(EXCLUDED.context, economy_base.context),
              content = COALESCE(EXCLUDED.content, economy_base.content),
              updated_at = now()
            """,
            (market, Jsonb(context) if context is not None else None, content),
        )


def get_daily(market: str, date: date_cls) -> dict[str, Any] | None:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT market, date, index_values, foreign_net, institution_net,
                   context, events, content, created_at
              FROM economy_daily WHERE market=%s AND date=%s
            """,
            (market, date),
        )
        return cur.fetchone()


def get_daily_latest(market: str) -> dict[str, Any] | None:
    """해당 market 의 가장 최근 economy_daily (date 미지정 시)."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT market, date, index_values, foreign_net, institution_net,
                   context, events, content, created_at
              FROM economy_daily WHERE market=%s
             ORDER BY date DESC LIMIT 1
            """,
            (market,),
        )
        return cur.fetchone()


def upsert_daily(
    market: str,
    date: date_cls,
    *,
    index_values: dict | None = None,
    foreign_net: int | None = None,
    institution_net: int | None = None,
    context: dict | None = None,
    events: list | None = None,
    content: str | None = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO economy_daily (market, date, index_values, foreign_net, institution_net,
                                        context, events, content)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (market, date) DO UPDATE SET
              index_values    = COALESCE(EXCLUDED.index_values, economy_daily.index_values),
              foreign_net     = COALESCE(EXCLUDED.foreign_net, economy_daily.foreign_net),
              institution_net = COALESCE(EXCLUDED.institution_net, economy_daily.institution_net),
              context         = COALESCE(EXCLUDED.context, economy_daily.context),
              events          = COALESCE(EXCLUDED.events, economy_daily.events),
              content         = COALESCE(EXCLUDED.content, economy_daily.content)
            """,
            (
                market, date,
                Jsonb(index_values) if index_values is not None else None,
                foreign_net, institution_net,
                Jsonb(context) if context is not None else None,
                Jsonb(events) if events is not None else None,
                content,
            ),
        )
