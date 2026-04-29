"""
재무 분석.
scrapers.dart 가 raw 재무제표를 제공하고, 이 모듈은 비율·성장률·서프라이즈·점수로 변환.
순수 함수 (DB 접근 X).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def compute_financial_ratios(
    per: float | None = None,
    pbr: float | None = None,
    price: float | None = None,
    eps: float | None = None,
    bps: float | None = None,
    revenue: float | None = None,
    op_profit: float | None = None,
    net_profit: float | None = None,
    total_assets: float | None = None,
    total_equity: float | None = None,
    total_debt: float | None = None,
    fcf: float | None = None,
    shares_outstanding: float | None = None,
) -> dict[str, float | None]:
    """
    원장 데이터 → 12개 핵심 비율 계산.
    입력 빈 값은 None 으로 스킵.
    """
    ratios: dict[str, float | None] = {
        "per": per,
        "pbr": pbr,
        "eps": eps,
        "bps": bps,
        "psr": None,
        "ev_ebitda": None,
        "roe": None,
        "roa": None,
        "op_margin": None,
        "net_margin": None,
        "debt_ratio": None,
        "fcf_yield": None,
    }

    # PER / PBR 직접 계산 (입력 누락 시)
    if per is None and price is not None and eps is not None and eps > 0:
        ratios["per"] = round(price / eps, 2)
    if pbr is None and price is not None and bps is not None and bps > 0:
        ratios["pbr"] = round(price / bps, 2)

    if revenue and revenue > 0:
        if shares_outstanding and price:
            market_cap = price * shares_outstanding
            ratios["psr"] = round(market_cap / revenue, 2)
        if op_profit is not None:
            ratios["op_margin"] = round(op_profit / revenue * 100, 2)
        if net_profit is not None:
            ratios["net_margin"] = round(net_profit / revenue * 100, 2)

    if total_equity and total_equity > 0 and net_profit is not None:
        ratios["roe"] = round(net_profit / total_equity * 100, 2)
    if total_assets and total_assets > 0 and net_profit is not None:
        ratios["roa"] = round(net_profit / total_assets * 100, 2)

    if total_equity and total_equity > 0 and total_debt is not None:
        ratios["debt_ratio"] = round(total_debt / total_equity * 100, 2)

    if fcf is not None and shares_outstanding and price and shares_outstanding > 0:
        market_cap = price * shares_outstanding
        if market_cap > 0:
            ratios["fcf_yield"] = round(fcf / market_cap * 100, 2)

    return ratios


def compute_growth_rates(quarterly: list[dict]) -> dict[str, float | None]:
    """
    분기별 재무 8분기 이상 입력 → QoQ/YoY 성장률.

    Input: [{year, quarter, revenue, op_profit, net_profit, eps}, ...] (최신이 마지막)
    """
    if len(quarterly) < 2:
        return {k: None for k in ["revenue_qoq", "revenue_yoy", "op_profit_qoq",
                                   "op_profit_yoy", "net_profit_yoy", "eps_yoy"]}

    latest = quarterly[-1]
    prev_quarter = quarterly[-2] if len(quarterly) >= 2 else None
    prev_year = quarterly[-5] if len(quarterly) >= 5 else None

    def pct(curr: float | None, prev: float | None) -> float | None:
        if curr is None or prev is None or prev == 0:
            return None
        return round((curr - prev) / abs(prev) * 100, 2)

    return {
        "revenue_qoq":    pct(latest.get("revenue"),    (prev_quarter or {}).get("revenue")),
        "revenue_yoy":    pct(latest.get("revenue"),    (prev_year or {}).get("revenue")),
        "op_profit_qoq":  pct(latest.get("op_profit"),  (prev_quarter or {}).get("op_profit")),
        "op_profit_yoy":  pct(latest.get("op_profit"),  (prev_year or {}).get("op_profit")),
        "net_profit_yoy": pct(latest.get("net_profit"), (prev_year or {}).get("net_profit")),
        "eps_yoy":        pct(latest.get("eps"),        (prev_year or {}).get("eps")),
    }


def detect_earnings_surprise(
    actual: float,
    consensus: float,
    std_error: float | None = None,
) -> dict[str, Any]:
    """
    실적 서프라이즈 판정.
    std_error 제공 시 z-score 기반 magnitude 분류.
    """
    if consensus == 0:
        return {"surprise_pct": None, "verdict": "inline", "magnitude": "weak"}

    surprise_pct = round((actual - consensus) / abs(consensus) * 100, 2)

    if abs(surprise_pct) < 3:
        verdict = "inline"
        magnitude = "weak"
    else:
        verdict = "beat" if surprise_pct > 0 else "miss"
        if std_error and std_error > 0:
            z = (actual - consensus) / std_error
            magnitude = "strong" if abs(z) > 1.5 else "mild"
        else:
            magnitude = "strong" if abs(surprise_pct) > 10 else "mild"

    return {"surprise_pct": surprise_pct, "verdict": verdict, "magnitude": magnitude}


def analyze_trend(series: list[float], periods: int = 8) -> str:
    """
    선형 회귀 기울기 기반 트렌드 판정.
    'improving' | 'deteriorating' | 'flat'
    """
    s = [x for x in series[-periods:] if x is not None]
    if len(s) < 3:
        return "flat"

    n = len(s)
    x_mean = (n - 1) / 2
    y_mean = sum(s) / n
    numer = sum((i - x_mean) * (s[i] - y_mean) for i in range(n))
    denom = sum((i - x_mean) ** 2 for i in range(n))
    slope = numer / denom if denom != 0 else 0

    rel = slope / abs(y_mean) if y_mean != 0 else 0
    if rel > 0.02:
        return "improving"
    if rel < -0.02:
        return "deteriorating"
    return "flat"


def compute_financial_score(
    ratios: dict[str, float | None],
    growth: dict[str, float | None] | None = None,
) -> int:
    """
    0~100 재무 점수. 단순 룰 기반 (나중에 백테스트로 튜닝 가능).
    """
    score = 50.0  # 중립 기준

    # ROE 가점 (15% 이상 우수)
    roe = ratios.get("roe")
    if roe is not None:
        if roe >= 20: score += 15
        elif roe >= 15: score += 10
        elif roe >= 10: score += 5
        elif roe < 0: score -= 20
        elif roe < 5: score -= 10

    # 영업이익률 가점
    op = ratios.get("op_margin")
    if op is not None:
        if op >= 30: score += 15
        elif op >= 15: score += 8
        elif op >= 5: score += 3
        elif op < 0: score -= 15

    # 부채비율 감점
    dr = ratios.get("debt_ratio")
    if dr is not None:
        if dr > 200: score -= 15
        elif dr > 150: score -= 8
        elif dr > 100: score -= 3

    # 성장률 가점
    if growth:
        yoy = growth.get("revenue_yoy")
        if yoy is not None:
            if yoy >= 30: score += 10
            elif yoy >= 15: score += 5
            elif yoy < -10: score -= 10

        op_yoy = growth.get("op_profit_yoy")
        if op_yoy is not None:
            if op_yoy >= 50: score += 10
            elif op_yoy >= 20: score += 5
            elif op_yoy < -30: score -= 10

    # FCF 가점
    fcf_y = ratios.get("fcf_yield")
    if fcf_y is not None:
        if fcf_y >= 5: score += 5
        elif fcf_y < 0: score -= 5

    return max(0, min(100, int(round(score))))


def summarize_health(
    ratios: dict[str, float | None],
    growth: dict[str, float | None] | None,
    score: int,
) -> str:
    """Claude가 받아서 그대로 or 재해석하는 한 문단 요약."""
    bullets: list[str] = []
    if ratios.get("roe") is not None:
        bullets.append(f"ROE {ratios['roe']}%")
    if ratios.get("op_margin") is not None:
        bullets.append(f"영업이익률 {ratios['op_margin']}%")
    if ratios.get("debt_ratio") is not None:
        bullets.append(f"부채비율 {ratios['debt_ratio']}%")
    if ratios.get("per") is not None:
        bullets.append(f"PER {ratios['per']}")
    if growth and growth.get("revenue_yoy") is not None:
        bullets.append(f"매출 YoY {growth['revenue_yoy']}%")
    if growth and growth.get("op_profit_yoy") is not None:
        bullets.append(f"영업익 YoY {growth['op_profit_yoy']}%")

    grade = (
        "A급 (재무 견고)" if score >= 85
        else "B급 (양호)" if score >= 70
        else "C급 (평범)" if score >= 50
        else "D급 (취약)"
    )
    return f"{grade} · score {score}/100 · " + " / ".join(bullets)
