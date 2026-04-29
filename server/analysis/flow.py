"""
수급 분석.
입력: 기관/외국인/공매도 일별 시계열
출력: 매집/분산 판정, 이상거래, z-score
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _summary_stats(series: pd.Series) -> dict:
    clean = series.dropna()
    if len(clean) == 0:
        return {"mean": None, "std": None, "latest": None, "z": None}
    mean = float(clean.mean())
    std = float(clean.std())
    latest = float(clean.iloc[-1])
    z = (latest - mean) / std if std > 0 else 0.0
    return {"mean": mean, "std": std, "latest": latest, "z": round(z, 2)}


def _trend(series: pd.Series, window: int = 5) -> str:
    """최근 window일 합계 부호로 트렌드 판정."""
    if len(series) < window:
        return "neutral"
    recent = series.tail(window).sum()
    if recent > 0:
        return "accumulating"
    if recent < 0:
        return "distributing"
    return "neutral"


def analyze_investor_flow(df: pd.DataFrame, window: int = 20) -> dict:
    """
    df: columns [날짜, 기관순매매, 외국인순매매]  (네이버 fetch_investor 결과)
    """
    if df.empty:
        return {"error": "no data"}
    df = df.copy().sort_values("날짜").tail(window)

    inst = pd.to_numeric(df["기관순매매"], errors="coerce")
    foreign = pd.to_numeric(df["외국인순매매"], errors="coerce")

    return {
        "window_days": window,
        "institutional": {
            "net_total": int(inst.sum()),
            "trend": _trend(inst),
            **_summary_stats(inst),
        },
        "foreign": {
            "net_total": int(foreign.sum()),
            "trend": _trend(foreign),
            **_summary_stats(foreign),
        },
        "abnormal_days": _detect_abnormal(df, inst, foreign),
    }


def _detect_abnormal(df: pd.DataFrame, inst: pd.Series, foreign: pd.Series) -> list[dict]:
    """z-score ±2σ 넘는 날."""
    out = []
    for col, series in [("기관", inst), ("외국인", foreign)]:
        mean, std = series.mean(), series.std()
        if std == 0 or np.isnan(std):
            continue
        for idx, val in series.items():
            if pd.isna(val):
                continue
            z = (val - mean) / std
            if abs(z) > 2:
                out.append({
                    "date": str(df.loc[idx, "날짜"]),
                    "type": col,
                    "value": int(val),
                    "z": round(float(z), 2),
                })
    return out[:10]


def analyze_shorting(df: pd.DataFrame) -> dict:
    """
    df: columns [날짜, 거래대금_공매도, 거래대금_전체] (KRX 공매도 거래)
    """
    if df.empty:
        return {"error": "no data"}
    df = df.copy().sort_values("날짜")
    if "공매도_거래대금" in df.columns and "거래대금" in df.columns:
        ratio = df["공매도_거래대금"] / df["거래대금"] * 100
    else:
        ratio = pd.Series([])

    return {
        "latest_ratio_pct": round(float(ratio.iloc[-1]), 2) if len(ratio) else None,
        "avg_ratio_pct": round(float(ratio.mean()), 2) if len(ratio) else None,
        "trend": _trend(ratio.diff().fillna(0)) if len(ratio) else None,
    }
