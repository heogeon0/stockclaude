"""portfolio_snapshots 테이블 (일일 포트폴리오 종합 + 액션 플랜)."""

from __future__ import annotations

from datetime import date as date_cls
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from server.db import get_conn


def save(
    user_id: UUID,
    date: date_cls,
    *,
    per_stock_summary: list[dict[str, Any]] | None = None,
    risk_flags: list[dict[str, Any]] | None = None,
    action_plan: list[dict[str, Any]] | None = None,
    headline: str | None = None,
    summary_content: str | None = None,
    kr_total_krw: int | None = None,
    us_total_usd: float | None = None,
    krw_usd_rate: float | None = None,
    total_krw: int | None = None,
    unrealized_pnl: int | None = None,
    realized_pnl_daily: int | None = None,
    realized_pnl_cumulative: int | None = None,
    cash_krw: int | None = None,
    cash_usd: float | None = None,
    weights: dict[str, Any] | None = None,
    sector_weights: dict[str, Any] | None = None,
) -> None:
    """Upsert — 같은 (user_id, date) 덮어쓰기."""
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO portfolio_snapshots (
              user_id, date,
              kr_total_krw, us_total_usd, krw_usd_rate, total_krw,
              unrealized_pnl, realized_pnl_daily, realized_pnl_cumulative,
              cash_krw, cash_usd, weights, sector_weights,
              per_stock_summary, risk_flags, action_plan,
              headline, summary_content
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (user_id, date) DO UPDATE SET
              kr_total_krw           = EXCLUDED.kr_total_krw,
              us_total_usd           = EXCLUDED.us_total_usd,
              krw_usd_rate           = EXCLUDED.krw_usd_rate,
              total_krw              = EXCLUDED.total_krw,
              unrealized_pnl         = EXCLUDED.unrealized_pnl,
              realized_pnl_daily     = EXCLUDED.realized_pnl_daily,
              realized_pnl_cumulative= EXCLUDED.realized_pnl_cumulative,
              cash_krw               = EXCLUDED.cash_krw,
              cash_usd               = EXCLUDED.cash_usd,
              weights                = EXCLUDED.weights,
              sector_weights         = EXCLUDED.sector_weights,
              per_stock_summary      = EXCLUDED.per_stock_summary,
              risk_flags             = EXCLUDED.risk_flags,
              action_plan            = EXCLUDED.action_plan,
              headline               = EXCLUDED.headline,
              summary_content        = EXCLUDED.summary_content
            """,
            (
                user_id, date,
                kr_total_krw, us_total_usd, krw_usd_rate, total_krw,
                unrealized_pnl, realized_pnl_daily, realized_pnl_cumulative,
                cash_krw, cash_usd,
                Jsonb(weights or {}), Jsonb(sector_weights or {}),
                Jsonb(per_stock_summary or []),
                Jsonb(risk_flags or []),
                Jsonb(action_plan or []),
                headline, summary_content,
            ),
        )


def get(user_id: UUID, date: date_cls) -> dict[str, Any] | None:
    """단일 날짜 스냅샷 조회."""
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM portfolio_snapshots WHERE user_id=%s AND date=%s",
            (user_id, date),
        )
        return cur.fetchone()


def get_latest_before(user_id: UUID, date: date_cls) -> dict[str, Any] | None:
    """해당 date 이전 가장 최근 스냅샷 (어제 리마인드용)."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT * FROM portfolio_snapshots
             WHERE user_id=%s AND date < %s
             ORDER BY date DESC LIMIT 1
            """,
            (user_id, date),
        )
        return cur.fetchone()


def get_latest(user_id: UUID) -> dict[str, Any] | None:
    """가장 최근 스냅샷 (date 지정 없을 때)."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT * FROM portfolio_snapshots
             WHERE user_id=%s
             ORDER BY date DESC LIMIT 1
            """,
            (user_id,),
        )
        return cur.fetchone()


def get_range(user_id: UUID, week_start: date_cls, week_end: date_cls) -> list[dict[str, Any]]:
    """주간 회고용 — 한 주 5~7 row 시계열 조회.

    라운드: 2026-05 weekly-review overhaul
    prepare_weekly_review_portfolio 의 portfolio_timeseries 카테고리 데이터.
    JSONB 컬럼 (per_stock_summary / risk_flags / action_plan / weights / sector_weights) 전체 포함.
    """
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT * FROM portfolio_snapshots
             WHERE user_id = %s AND date BETWEEN %s AND %s
             ORDER BY date ASC
            """,
            (user_id, week_start, week_end),
        )
        return cur.fetchall()


def reconcile(user_id: UUID, date: date_cls) -> dict[str, Any]:
    """
    해당 date 의 action_plan 을 trades 와 매칭해 status 업데이트.

    매칭 규칙:
      - action.code == trade.code
      - action.action == trade.side (buy/sell)
      - trade.executed_at::date >= action.created_date (= snapshot.date)
      - action.status IN ('pending','conditional') 만 대상
    매칭되면 status='executed', executed_trade_id=trade.id
    매칭 못 하고 expires_at 이 과거면 status='expired'.
    """
    snap = get(user_id, date)
    if not snap:
        return {"updated": 0, "reason": "snapshot not found"}

    actions = snap.get("action_plan") or []
    if not actions:
        return {"updated": 0, "reason": "no actions"}

    updated = 0
    with get_conn() as conn:
        # 해당 snapshot date 이후 체결된 trades 전부 로드
        cur = conn.execute(
            """
            SELECT id, code, side, executed_at
              FROM trades
             WHERE user_id=%s AND executed_at::date >= %s
             ORDER BY executed_at
            """,
            (user_id, date),
        )
        trades = cur.fetchall()

    now = __import__("datetime").datetime.now(tz=__import__("datetime").timezone.utc)
    used_trade_ids: set[int] = set()

    # 이미 executed 로 기록된 action 의 trade id 선점 (중복 매칭 방지)
    for act in actions:
        if act.get("status") == "executed":
            tid = act.get("executed_trade_id")
            if isinstance(tid, int):
                used_trade_ids.add(tid)

    for act in actions:
        if act.get("status") not in ("pending", "conditional"):
            continue
        # 1) 체결 매칭
        for t in trades:
            if t["id"] in used_trade_ids:
                continue
            if t["code"] == act.get("code") and t["side"] == act.get("action"):
                act["status"] = "executed"
                act["executed_trade_id"] = t["id"]
                used_trade_ids.add(t["id"])
                updated += 1
                break
        else:
            # 2) 만료 체크
            exp = act.get("expires_at")
            if exp:
                try:
                    exp_dt = __import__("datetime").datetime.fromisoformat(exp)
                    if exp_dt.tzinfo is None:
                        exp_dt = exp_dt.replace(tzinfo=__import__("datetime").timezone.utc)
                    if exp_dt < now:
                        act["status"] = "expired"
                        updated += 1
                except (ValueError, TypeError):
                    pass

    # action_plan 업데이트 저장
    with get_conn() as conn:
        conn.execute(
            "UPDATE portfolio_snapshots SET action_plan=%s WHERE user_id=%s AND date=%s",
            (Jsonb(actions), user_id, date),
        )

    return {
        "updated": updated,
        "total_actions": len(actions),
        "matched_trade_ids": sorted(used_trade_ids),
    }
