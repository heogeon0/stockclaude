"""
거시 변수 민감도.
금리·환율·유가·VIX 와 종목 수익률 간 회귀 베타.
"""

from __future__ import annotations

import pandas as pd


def _align_returns(
    stock_close: pd.Series,
    macro_series: pd.Series,
    min_samples: int = 60,
) -> pd.DataFrame | None:
    """두 series를 날짜 기준 정렬 + 수익률(차분) 변환."""
    merged = pd.DataFrame({
        "stock_ret": stock_close.pct_change(),
        "macro_change": macro_series.diff(),
    }).dropna()
    if len(merged) < min_samples:
        return None
    return merged


def compute_macro_beta(
    stock_close: pd.Series,
    macro_series: pd.Series,
    macro_name: str = "macro",
) -> dict:
    """
    회귀: stock_ret = α + β * macro_change
    """
    merged = _align_returns(stock_close, macro_series)
    if merged is None:
        return {"beta": None, "r_squared": None, "n": 0, "macro": macro_name}

    cov = merged["stock_ret"].cov(merged["macro_change"])
    var = merged["macro_change"].var()
    beta = cov / var if var > 0 else None
    corr = merged["stock_ret"].corr(merged["macro_change"])
    r_sq = corr ** 2 if corr is not None else None

    return {
        "macro": macro_name,
        "beta": round(float(beta), 4) if beta is not None else None,
        "r_squared": round(float(r_sq), 3) if r_sq is not None else None,
        "n": len(merged),
        "interpretation": _interpret(beta, macro_name),
    }


def _interpret(beta: float | None, macro_name: str) -> str:
    if beta is None:
        return "insufficient data"
    mag = abs(beta)
    sign = "+" if beta > 0 else "-"
    label = "low" if mag < 0.3 else "moderate" if mag < 1 else "high"
    return f"{sign} {label} sensitivity to {macro_name}"


def multi_factor_sensitivity(
    stock_close: pd.Series,
    macros: dict[str, pd.Series],
) -> dict:
    """여러 매크로에 대한 베타 동시 계산."""
    return {name: compute_macro_beta(stock_close, series, name) for name, series in macros.items()}
