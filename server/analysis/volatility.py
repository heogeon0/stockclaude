"""
변동성·리스크 지표.
- 실현변동성 (realized vol, Parkinson)
- 베타 (시장 대비)
- 최대 낙폭 (drawdown)
- 변동성 regime 분류
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def realized_volatility(df: pd.DataFrame, window: int = 30, annualize: bool = True) -> float | None:
    """
    종가 기반 일간 수익률 표준편차. 연율화 시 √252 곱.
    """
    if df is None or df.empty or len(df) < window + 1:
        return None
    close = df["종가"] if "종가" in df.columns else df["close"]
    returns = close.pct_change().dropna().tail(window)
    if returns.empty:
        return None
    vol = float(returns.std())
    if annualize:
        vol *= (252 ** 0.5)
    return round(vol * 100, 2)  # %


def parkinson_volatility(df: pd.DataFrame, window: int = 30) -> float | None:
    """Parkinson 변동성 (high-low 기반, 더 효율적 추정)."""
    if df is None or df.empty or len(df) < window:
        return None
    tail = df.tail(window)
    hi = tail["고가"] if "고가" in tail.columns else tail["high"]
    lo = tail["저가"] if "저가" in tail.columns else tail["low"]
    log_hl = np.log(hi.astype(float) / lo.astype(float))
    park = float(np.sqrt((log_hl ** 2).mean() / (4 * np.log(2))))
    return round(park * np.sqrt(252) * 100, 2)


def compute_beta(stock_df: pd.DataFrame, benchmark_df: pd.DataFrame) -> dict:
    """
    베타 = cov(stock, market) / var(market).
    stock_df, benchmark_df: 둘 다 '날짜','종가' 컬럼 필요.
    """
    s_close = stock_df["종가"] if "종가" in stock_df.columns else stock_df["close"]
    b_close = benchmark_df["종가"] if "종가" in benchmark_df.columns else benchmark_df["close"]

    merged = pd.DataFrame({
        "stock": s_close.pct_change(),
        "bench": b_close.pct_change(),
    }).dropna()
    if len(merged) < 30:
        return {"beta": None, "r_squared": None, "n": len(merged)}

    cov = merged["stock"].cov(merged["bench"])
    var = merged["bench"].var()
    beta = cov / var if var > 0 else None
    corr = merged["stock"].corr(merged["bench"])
    r_sq = corr ** 2 if corr is not None else None

    return {
        "beta": round(float(beta), 3) if beta is not None else None,
        "r_squared": round(float(r_sq), 3) if r_sq is not None else None,
        "n": len(merged),
    }


def compute_drawdown(df: pd.DataFrame) -> dict:
    """최대 낙폭 + 현재 낙폭 + 회복 일수."""
    if df is None or df.empty:
        return {"max_dd": None, "current_dd": None}
    close = df["종가"] if "종가" in df.columns else df["close"]
    cum_max = close.cummax()
    dd = (close - cum_max) / cum_max

    max_dd = float(dd.min())
    current_dd = float(dd.iloc[-1])

    # 피크에서부터 지속 일수
    peak_idx = cum_max.idxmax()
    days_from_peak = len(df) - int(peak_idx) - 1 if not pd.isna(peak_idx) else 0

    return {
        "max_dd_pct": round(max_dd * 100, 2),
        "current_dd_pct": round(current_dd * 100, 2),
        "days_from_peak": days_from_peak,
    }


def classify_vol_regime(realized: float | None) -> str:
    """연율 변동성 기준 분류 (주식 기준)."""
    if realized is None:
        return "unknown"
    if realized < 15:
        return "low"
    if realized < 25:
        return "normal"
    if realized < 40:
        return "high"
    return "extreme"
