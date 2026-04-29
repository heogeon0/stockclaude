"""analyst_reports 테이블 + v_analyst_consensus 뷰."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from psycopg.types.json import Jsonb

from server.db import get_conn


def record_report(
    code: str,
    broker: str,
    published_at: datetime,
    *,
    broker_country: str | None = None,
    analyst: str | None = None,
    report_url: str | None = None,
    title: str | None = None,
    rating: str | None = None,
    rating_change: str | None = None,
    previous_rating: str | None = None,
    target_price: Decimal | None = None,
    previous_target_price: Decimal | None = None,
    currency: str = "KRW",
    forecasts: dict | None = None,
    summary: str | None = None,
    key_thesis: str | None = None,
    risks: str | None = None,
) -> int | None:
    """
    URL 중복 시 스킵(ON CONFLICT DO NOTHING). Returns: inserted id or None.
    """
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO analyst_reports (
                code, broker, broker_country, analyst, published_at, report_url, title,
                rating, rating_change, previous_rating,
                target_price, previous_target_price, currency,
                forecasts, summary, key_thesis, risks
            ) VALUES (%s, %s, %s, %s, %s, %s, %s,
                      %s, %s, %s,
                      %s, %s, %s,
                      %s, %s, %s, %s)
            ON CONFLICT (report_url) DO NOTHING
            RETURNING id
            """,
            (
                code, broker, broker_country, analyst, published_at, report_url, title,
                rating, rating_change, previous_rating,
                target_price, previous_target_price, currency,
                Jsonb(forecasts if forecasts is not None else {}),
                summary, key_thesis, risks,
            ),
        )
        row = cur.fetchone()
        return row["id"] if row else None


def list_recent(code: str, days: int = 30) -> list[dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT broker, analyst, published_at, rating, rating_change,
                   target_price, previous_target_price, upside_pct, summary
              FROM analyst_reports
             WHERE code = %s
               AND published_at > now() - make_interval(days => %s)
             ORDER BY published_at DESC
            """,
            (code, days),
        )
        return cur.fetchall()


def get_consensus(code: str) -> dict[str, Any] | None:
    """v_analyst_consensus 뷰 조회."""
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM v_analyst_consensus WHERE code = %s", (code,))
        return cur.fetchone()
