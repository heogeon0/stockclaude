"""server.analysis.momentum.dual_momentum_signal 유닛 테스트.

4 가지 시그널 분기 (절대×상대 진리표) + 데이터 부족 케이스.
"""
from __future__ import annotations

import pandas as pd

from server.analysis.momentum import dual_momentum_signal


def test_dual_momentum_buy_when_both_positive(linear_ramp_ohlcv: pd.DataFrame, benchmark_flat_ohlcv: pd.DataFrame):
    """종목 +30%, 벤치 +10% — 절대(>3.5%) + 상대(>벤치) 모두 양수 → Buy."""
    out = dual_momentum_signal(linear_ramp_ohlcv, benchmark_flat_ohlcv)
    assert out["시그널"] == "Buy"
    assert bool(out["절대_모멘텀"])
    assert bool(out["상대_모멘텀"])
    assert out["절대_수익률_12M"] == 30.0
    assert out["벤치마크_초과_12M"] == 20.0  # 30 - 10


def test_dual_momentum_cash_when_below_benchmark(linear_ramp_ohlcv: pd.DataFrame):
    """종목 +30%, 벤치 +50% — 절대 양수지만 벤치 하회 → Cash."""
    import numpy as np

    bench_close = np.linspace(100.0, 150.0, 252)
    bench_df = pd.DataFrame({
        "날짜": linear_ramp_ohlcv["날짜"].values,
        "시가": bench_close, "고가": bench_close * 1.01, "저가": bench_close * 0.99,
        "종가": bench_close, "거래량": [1_000_000] * 252,
    })
    out = dual_momentum_signal(linear_ramp_ohlcv, bench_df)
    assert out["시그널"] == "Cash"
    assert bool(out["절대_모멘텀"])
    assert not bool(out["상대_모멘텀"])


def test_dual_momentum_cash_when_above_benchmark_but_below_riskfree(declining_ohlcv: pd.DataFrame, benchmark_decline_ohlcv: pd.DataFrame):
    """종목 -10%, 벤치 +2% — 둘 다 약세 → Cash.

    declining(-10) > decline(+2) 는 거짓이라 양쪽 다 False가 정확함.
    """
    out = dual_momentum_signal(declining_ohlcv, benchmark_decline_ohlcv)
    assert out["시그널"] == "Cash"
    assert not bool(out["절대_모멘텀"])
    assert not bool(out["상대_모멘텀"])


def test_dual_momentum_insufficient_data():
    """데이터 252행 미만 → 오류 키 + Cash."""
    df = pd.DataFrame({"종가": [100.0] * 100})
    out = dual_momentum_signal(df, df)
    assert "오류" in out
    assert out["시그널"] == "Cash"
