"""
이벤트 감지.
- 실적 D-N 알림 (DART fetch_next_earnings_date + current date)
- 52주 고저 돌파 (OHLCV 기반)
- 집중도 경고 (positions + stocks join)
- Rating change (analyst_reports 최근 N일 upgrade/downgrade)
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pandas as pd


def earnings_proximity(next_earnings_date: date | None, today: date | None = None) -> dict | None:
    """D-N 계산. None 반환 시 예정 없음."""
    if next_earnings_date is None:
        return None
    today = today or date.today()
    delta = (next_earnings_date - today).days
    if delta < 0:
        return {"status": "past", "days": delta}

    action = "none"
    if delta <= 7:
        action = "tighten_stop_loss"
    elif delta <= 14:
        action = "review_position_size"

    return {
        "next_earnings_date": next_earnings_date.isoformat(),
        "days_until": delta,
        "status": f"D-{delta}" if delta > 0 else "D-0",
        "recommended_action": action,
    }


def detect_52week_break(df: pd.DataFrame) -> dict | None:
    """
    df: OHLCV + 고가/저가 포함. 52주 기준 돌파·이탈 감지.
    """
    if df is None or df.empty or len(df) < 20:
        return None
    df = df.copy().sort_values("날짜")
    recent_window = df.tail(252)  # 52주 ≈ 252 거래일

    hi52 = recent_window["고가"].max()
    lo52 = recent_window["저가"].min()
    close = df.iloc[-1]["종가"]
    high_today = df.iloc[-1]["고가"]
    low_today = df.iloc[-1]["저가"]

    breaks = []
    if high_today >= hi52:
        breaks.append({
            "type": "52w_high_breakout",
            "price": float(high_today),
            "close": float(close),
        })
    if low_today <= lo52:
        breaks.append({
            "type": "52w_low_breakdown",
            "price": float(low_today),
            "close": float(close),
        })

    return {
        "high_52w": float(hi52),
        "low_52w": float(lo52),
        "close_ratio_to_high": round(float(close / hi52) * 100, 2) if hi52 else None,
        "breaks": breaks,
    }


def detect_rating_changes(reports: list[dict], days: int = 7) -> list[dict]:
    """
    최근 N일 내 rating change (upgrade/downgrade/initiate) 필터.
    reports: analyst.list_recent() 결과.
    """
    from zoneinfo import ZoneInfo
    cutoff = datetime.now(tz=ZoneInfo("Asia/Seoul")) - timedelta(days=days)
    out = []
    for r in reports:
        pub = r.get("published_at")
        if isinstance(pub, str):
            pub = datetime.fromisoformat(pub)
        if pub is not None and pub.tzinfo is None:
            pub = pub.replace(tzinfo=ZoneInfo("Asia/Seoul"))
        if pub is None or pub < cutoff:
            continue
        if r.get("rating_change") in ("upgrade", "downgrade", "initiate"):
            prev = r.get("previous_target_price")
            curr = r.get("target_price")
            upside_added = None
            if prev and curr and prev > 0:
                upside_added = round(float((curr - prev) / prev * 100), 2)
            out.append({
                "broker": r.get("broker"),
                "change": r.get("rating_change"),
                "rating": r.get("rating"),
                "target_from": float(prev) if prev else None,
                "target_to": float(curr) if curr else None,
                "upside_added_pct": upside_added,
                "published_at": pub.isoformat() if pub else None,
            })
    return out


def detect_concentration_alerts(
    positions_data: list[dict],
    cash_data: dict,
    threshold_pct: float = 25.0,
) -> list[dict]:
    """
    positions: repos.positions.list_active() 결과
    cash: repos.cash.get_all() 결과
    """
    if not positions_data:
        return []
    # 시장별 집계
    alerts = []
    for market in ("kr", "us"):
        currency = "KRW" if market == "kr" else "USD"
        market_positions = [p for p in positions_data if p.get("market") == market]
        if not market_positions:
            continue
        total = sum(Decimal(str(p["cost_basis"] or 0)) for p in market_positions)
        total += Decimal(str(cash_data.get(currency, 0)))
        if total == 0:
            continue
        for p in market_positions:
            weight = float(Decimal(str(p["cost_basis"] or 0)) / total * 100)
            if weight > threshold_pct:
                alerts.append({
                    "code": p["code"],
                    "name": p.get("name"),
                    "weight_pct": round(weight, 2),
                    "threshold": threshold_pct,
                    "severity": "critical" if weight > 30 else "warning",
                })
    return alerts
