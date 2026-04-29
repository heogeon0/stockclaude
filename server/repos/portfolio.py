"""portfolio_snapshots + 통합 집계."""

from __future__ import annotations

from datetime import date as date_cls
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from server.db import get_conn


def compute_current_weights(user_id: UUID) -> dict[str, Any]:
    """
    현재 Active 포지션 + 예수금 기반 비중 계산.
    KR/USD 분리 반환 (환율 적용은 api 단에서).
    """
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT s.market, s.currency, p.code, s.name, p.qty, p.avg_price, p.cost_basis
              FROM positions p JOIN stocks s USING(code)
             WHERE p.user_id = %s AND p.status = 'Active'
             ORDER BY s.market, p.cost_basis DESC
            """,
            (user_id,),
        )
        active = cur.fetchall()

        cur = conn.execute(
            "SELECT currency, amount FROM cash_balance WHERE user_id = %s",
            (user_id,),
        )
        cash = {row["currency"]: row["amount"] for row in cur.fetchall()}

    kr_total = sum(
        (p["cost_basis"] or Decimal(0)) for p in active if p["market"] == "kr"
    ) + cash.get("KRW", Decimal(0))
    us_total = sum(
        (p["cost_basis"] or Decimal(0)) for p in active if p["market"] == "us"
    ) + cash.get("USD", Decimal(0))

    return {
        "positions": active,
        "cash": cash,
        "kr_total_krw": kr_total,
        "us_total_usd": us_total,
    }


def get_snapshot(user_id: UUID, date: date_cls) -> dict[str, Any] | None:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM portfolio_snapshots WHERE user_id = %s AND date = %s",
            (user_id, date),
        )
        return cur.fetchone()


def upsert_snapshot(
    user_id: UUID,
    date: date_cls,
    *,
    kr_total_krw: int | None = None,
    us_total_usd: Decimal | None = None,
    krw_usd_rate: Decimal | None = None,
    total_krw: int | None = None,
    unrealized_pnl: int | None = None,
    realized_pnl_daily: int | None = None,
    realized_pnl_cumulative: int | None = None,
    cash_krw: int | None = None,
    cash_usd: Decimal | None = None,
    weights: dict | None = None,
    sector_weights: dict | None = None,
    summary_content: str | None = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO portfolio_snapshots (
                user_id, date, kr_total_krw, us_total_usd, krw_usd_rate, total_krw,
                unrealized_pnl, realized_pnl_daily, realized_pnl_cumulative,
                cash_krw, cash_usd, weights, sector_weights, summary_content
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, date) DO UPDATE SET
              kr_total_krw = COALESCE(EXCLUDED.kr_total_krw, portfolio_snapshots.kr_total_krw),
              us_total_usd = COALESCE(EXCLUDED.us_total_usd, portfolio_snapshots.us_total_usd),
              krw_usd_rate = COALESCE(EXCLUDED.krw_usd_rate, portfolio_snapshots.krw_usd_rate),
              total_krw = COALESCE(EXCLUDED.total_krw, portfolio_snapshots.total_krw),
              unrealized_pnl = COALESCE(EXCLUDED.unrealized_pnl, portfolio_snapshots.unrealized_pnl),
              realized_pnl_daily = COALESCE(EXCLUDED.realized_pnl_daily, portfolio_snapshots.realized_pnl_daily),
              realized_pnl_cumulative = COALESCE(EXCLUDED.realized_pnl_cumulative, portfolio_snapshots.realized_pnl_cumulative),
              cash_krw = COALESCE(EXCLUDED.cash_krw, portfolio_snapshots.cash_krw),
              cash_usd = COALESCE(EXCLUDED.cash_usd, portfolio_snapshots.cash_usd),
              weights = COALESCE(EXCLUDED.weights, portfolio_snapshots.weights),
              sector_weights = COALESCE(EXCLUDED.sector_weights, portfolio_snapshots.sector_weights),
              summary_content = COALESCE(EXCLUDED.summary_content, portfolio_snapshots.summary_content)
            """,
            (
                user_id, date, kr_total_krw, us_total_usd, krw_usd_rate, total_krw,
                unrealized_pnl, realized_pnl_daily, realized_pnl_cumulative,
                cash_krw, cash_usd,
                Jsonb(weights) if weights is not None else None,
                Jsonb(sector_weights) if sector_weights is not None else None,
                summary_content,
            ),
        )
