"""
산업 메트릭 자동 산출 — industry-base v6 메트릭 (avg_per/avg_pbr/avg_roe/avg_op_margin/vol_baseline_30d).

leader_followers.leaders 종목들에 compute_financials + 30일 RV 돌려서 평균 산출.
LLM 이 industry-inline 에서 수동 산출하던 작업의 정형 MCP 대체.
"""
from __future__ import annotations

import statistics
from datetime import datetime
from typing import Any

import pandas as pd

from server.analysis.volatility import realized_volatility


def _safe_mean(vals: list[float | None]) -> float | None:
    cleaned = [v for v in vals if v is not None]
    if not cleaned:
        return None
    return round(statistics.mean(cleaned), 2)


def _fetch_ohlcv_30d(code: str, market: str) -> pd.DataFrame | None:
    """30일 RV 계산용 OHLCV (60일 fetch — pct_change 안정성)."""
    try:
        if market == "us":
            from server.scrapers import kis
            return kis.fetch_us_daily(code, days=60)
        else:
            from server.scrapers import kis
            return kis.fetch_period_ohlcv(code, days=60)
    except Exception:
        return None


def compute_industry_metrics(industry_code: str) -> dict[str, Any]:
    """
    leader_followers.leaders 종목에 재무·변동성 계산 → 산업 평균 산출.

    반환:
      {
        "industry_code": "...",
        "leaders": [{"code", "name", "per", "pbr", "roe", "op_margin", "vol_30d"}, ...],
        "avg_per": float | None,
        "avg_pbr": float | None,
        "avg_roe": float | None,
        "avg_op_margin": float | None,
        "vol_baseline_30d": float | None,
        "computed_at": "YYYY-MM-DD HH:MM",
        "errors": {code: error_msg, ...},
      }
    """
    from server.repos import industries as ind_repo, stocks as stocks_repo

    row = ind_repo.get_industry(industry_code)
    if not row:
        return {"error": f"industry not found: {industry_code}"}

    lf = row.get("leader_followers") or {}
    if isinstance(lf, str):
        # 일부 환경에서 jsonb 가 str 로 떨어질 수도 — graceful
        import json
        try:
            lf = json.loads(lf)
        except Exception:
            lf = {}
    leaders = (lf or {}).get("leaders") or []
    market = row.get("market") or "kr"

    # MCP 의 compute_financials 함수 직접 import (서버 모듈 우회 호출)
    from server.mcp.server import compute_financials as cf

    leader_rows: list[dict] = []
    errors: dict[str, str] = {}
    for code in leaders:
        s = stocks_repo.get_stock(code) or {}
        try:
            fin = cf(code, years=1)
        except Exception as e:
            errors[code] = f"compute_financials: {type(e).__name__}: {e}"[:200]
            fin = {}
        ratios = (fin or {}).get("ratios") or {}

        # vol 30d
        df = _fetch_ohlcv_30d(code, s.get("market") or market)
        vol = realized_volatility(df, window=30) if df is not None and not df.empty else None

        leader_rows.append({
            "code": code,
            "name": s.get("name"),
            "per": ratios.get("per"),
            "pbr": ratios.get("pbr"),
            "roe": ratios.get("roe"),
            "op_margin": ratios.get("op_margin"),
            "vol_30d": vol,
        })

    return {
        "industry_code": industry_code,
        "name": row.get("name"),
        "market": market,
        "leaders": leader_rows,
        "avg_per": _safe_mean([r["per"] for r in leader_rows]),
        "avg_pbr": _safe_mean([r["pbr"] for r in leader_rows]),
        "avg_roe": _safe_mean([r["roe"] for r in leader_rows]),
        "avg_op_margin": _safe_mean([r["op_margin"] for r in leader_rows]),
        "vol_baseline_30d": _safe_mean([r["vol_30d"] for r in leader_rows]),
        "computed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "errors": errors,
    }
