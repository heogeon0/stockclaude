"""
포트폴리오 상관 · 다각화 분석.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_correlation_matrix(price_dict: dict[str, pd.Series]) -> pd.DataFrame:
    """
    price_dict: {code: Series(날짜 index, 종가 value)}
    returns: 상관계수 행렬 (DataFrame)
    """
    if len(price_dict) < 2:
        return pd.DataFrame()
    df = pd.DataFrame(price_dict)
    returns = df.pct_change().dropna()
    return returns.corr()


def diversification_metrics(
    price_dict: dict[str, pd.Series],
    weights: dict[str, float] | None = None,
) -> dict:
    """
    포트 다각화 지표.
      - avg_pairwise: 평균 상관
      - effective_holdings: 실질 종목수 (1/sum(w²·(1+corr)))
      - max_corr_pair: 가장 상관 높은 2종목
    """
    corr = compute_correlation_matrix(price_dict)
    if corr.empty:
        return {"error": "need at least 2 stocks"}

    codes = list(corr.columns)
    n = len(codes)
    if weights is None:
        weights = {c: 1 / n for c in codes}

    # 평균 pairwise (대각 제외)
    triu = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
    pairs = triu.stack()
    avg = float(pairs.mean()) if len(pairs) else 0.0

    # max corr pair
    if len(pairs):
        idx = pairs.idxmax()
        max_pair = {"a": idx[0], "b": idx[1], "corr": round(float(pairs.max()), 3)}
    else:
        max_pair = None

    # effective holdings (단순 Herfindahl-like, 상관 반영)
    w = np.array([weights.get(c, 1 / n) for c in codes])
    cov_like = corr.fillna(0).values
    port_var_proxy = float(w @ cov_like @ w)
    eff = 1.0 / port_var_proxy if port_var_proxy > 0 else n

    # diversification score 0~100 (낮은 상관 = 높은 점수)
    score = int(max(0, min(100, 100 - avg * 100)))

    return {
        "avg_pairwise_corr": round(avg, 3),
        "effective_holdings": round(eff, 2),
        "most_correlated_pair": max_pair,
        "diversification_score": score,
        "codes": codes,
        "matrix": {c: {k: round(float(v), 3) for k, v in corr[c].items()} for c in codes},
    }
