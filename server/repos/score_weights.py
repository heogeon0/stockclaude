"""score_weight_defaults / overrides / history 접근."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from server.db import get_conn

VALID_TIMEFRAMES = {"day-trade", "swing", "long-term", "momentum"}
VALID_DIMS = {"재무", "산업", "경제", "기술", "밸류에이션"}


def get_defaults(timeframe: str) -> dict[str, Decimal]:
    assert timeframe in VALID_TIMEFRAMES, f"invalid timeframe: {timeframe}"
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT dim, weight FROM score_weight_defaults WHERE timeframe = %s",
            (timeframe,),
        )
        return {row["dim"]: row["weight"] for row in cur.fetchall()}


def list_all_defaults() -> list[dict[str, Any]]:
    """전체 기본 가중치 (4 timeframe × 5 dim = 20행)."""
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT timeframe, dim, weight FROM score_weight_defaults ORDER BY timeframe, dim"
        )
        return cur.fetchall()


def get_applied(code: str, timeframe: str) -> dict[str, Any]:
    """
    종목별 최종 적용 가중치 (override + default 병합).
    Returns:
      {
        'weights': {'재무': 0.15, '산업': 0.30, ...},
        'sources': {'재무': 'claude', '산업': 'default', ...},
      }
    """
    assert timeframe in VALID_TIMEFRAMES
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM get_applied_weights(%s, %s)", (code, timeframe))
        rows = cur.fetchall()
    return {
        "weights": {r["dim"]: r["weight"] for r in rows},
        "sources": {r["dim"]: r["source"] for r in rows},
    }


def set_override(
    code: str,
    timeframe: str,
    weights: dict[str, float | Decimal],
    reason: str,
    source: str = "claude",
    expires_at: datetime | None = None,
) -> None:
    """
    5개 차원 전체를 override (합계 ±0.01 검증).
    """
    assert timeframe in VALID_TIMEFRAMES
    assert set(weights.keys()) == VALID_DIMS, f"5개 차원 필수: {VALID_DIMS - set(weights.keys())}"
    assert source in ("user", "claude", "backtest")
    total = sum(Decimal(str(w)) for w in weights.values())
    assert abs(total - Decimal(1)) <= Decimal("0.01"), f"가중치 합계 {total} != 1.0"

    with get_conn() as conn:
        for dim, w in weights.items():
            conn.execute(
                """
                INSERT INTO score_weight_overrides (code, timeframe, dim, weight, reason, source, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (code, timeframe, dim) DO UPDATE SET
                  weight = EXCLUDED.weight,
                  reason = EXCLUDED.reason,
                  source = EXCLUDED.source,
                  expires_at = EXCLUDED.expires_at,
                  updated_at = now()
                """,
                (code, timeframe, dim, w, reason, source, expires_at),
            )


def reset_override(code: str, timeframe: str | None = None) -> int:
    """종목 override 제거 (default 복원). Returns: 제거 행수."""
    with get_conn() as conn:
        if timeframe:
            cur = conn.execute(
                "DELETE FROM score_weight_overrides WHERE code = %s AND timeframe = %s",
                (code, timeframe),
            )
        else:
            cur = conn.execute(
                "DELETE FROM score_weight_overrides WHERE code = %s", (code,),
            )
        return cur.rowcount


def list_overrides(include_expired: bool = False) -> list[dict[str, Any]]:
    sql = """
        SELECT o.code, s.name, o.timeframe, o.dim, o.weight, o.reason,
               o.source, o.expires_at, o.updated_at
          FROM score_weight_overrides o JOIN stocks s USING(code)
    """
    if not include_expired:
        sql += " WHERE o.expires_at IS NULL OR o.expires_at > now()"
    sql += " ORDER BY o.code, o.timeframe, o.dim"
    with get_conn() as conn:
        cur = conn.execute(sql)
        return cur.fetchall()


def get_history(code: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    sql = """
        SELECT code, timeframe, dim, old_weight, new_weight, reason, source, changed_at
          FROM score_weight_history
    """
    params: tuple = ()
    if code:
        sql += " WHERE code = %s"
        params = (code,)
    sql += " ORDER BY changed_at DESC LIMIT %s"
    params = (*params, limit)
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall()
