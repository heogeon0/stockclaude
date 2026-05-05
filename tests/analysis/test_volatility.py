"""server.analysis.volatility 유닛 테스트.

순수 함수 — DB 의존 X. 한글 컬럼 OHLCV 픽스처(conftest.py)로 호출.
손계산 가능한 작은 DataFrame으로 정확값 검증.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from server.analysis.volatility import (
    classify_vol_regime,
    compute_beta,
    compute_drawdown,
    parkinson_volatility,
    realized_volatility,
)


# ---------------------------------------------------------------------------
# compute_drawdown
# ---------------------------------------------------------------------------


def test_drawdown_known_peak_trough(drawdown_ohlcv: pd.DataFrame):
    """[100, 110, 95, 90, 95] — peak 110, trough 90, max_dd = (90-110)/110 = -18.18%."""
    out = compute_drawdown(drawdown_ohlcv)
    assert out["max_dd_pct"] == pytest.approx(-18.18, abs=0.01)
    # 마지막 종가 95, 직전 peak 110 → current_dd = (95-110)/110 = -13.64%
    assert out["current_dd_pct"] == pytest.approx(-13.64, abs=0.01)
    # peak는 idx=1 (가격 110), 마지막 idx=4 → days_from_peak = 4-1 = 3
    assert out["days_from_peak"] == 3


def test_drawdown_constant_prices(constant_ohlcv: pd.DataFrame):
    """가격이 일정하면 낙폭 0."""
    out = compute_drawdown(constant_ohlcv)
    assert out["max_dd_pct"] == 0.0
    assert out["current_dd_pct"] == 0.0


def test_drawdown_empty_df():
    """빈 DataFrame은 None 응답."""
    out = compute_drawdown(pd.DataFrame({"종가": []}))
    assert out["max_dd"] is None
    assert out["current_dd"] is None


# ---------------------------------------------------------------------------
# realized_volatility
# ---------------------------------------------------------------------------


def test_realized_vol_constant_returns(constant_ohlcv: pd.DataFrame):
    """가격 변동 0 → 일간 수익률 std=0 → 변동성 0."""
    assert realized_volatility(constant_ohlcv, window=30) == 0.0


def test_realized_vol_insufficient_data():
    """window+1 미만이면 None."""
    df = pd.DataFrame({"종가": [100.0] * 10})
    assert realized_volatility(df, window=30) is None


def test_realized_vol_known_alternating():
    """[100, 101, 100, 101, ...] 31행 → 매일 ±1% 등락 → std=0.01, 연율화 vol = 0.01*√252*100 ≈ 15.87%."""
    closes = np.array([100.0 if i % 2 == 0 else 101.0 for i in range(31)])
    df = pd.DataFrame({"종가": closes})
    vol = realized_volatility(df, window=30, annualize=True)
    # returns = [+0.01, -0.0099, +0.01, ...] approx ±0.01, std ≈ 0.01005
    expected = 0.01005 * math.sqrt(252) * 100  # ≈ 15.95
    assert vol == pytest.approx(expected, abs=0.5)


# ---------------------------------------------------------------------------
# parkinson_volatility
# ---------------------------------------------------------------------------


def test_parkinson_vol_no_intraday_range():
    """high == low → log(1)=0 → parkinson 0."""
    n = 30
    df = pd.DataFrame({"고가": [100.0] * n, "저가": [100.0] * n})
    assert parkinson_volatility(df, window=30) == 0.0


def test_parkinson_vol_known_constant_range():
    """매일 high=101, low=99 → log(101/99) ≈ 0.02000.
    park = sqrt((0.02000^2)/(4*ln2)) ≈ 0.01202
    annualized %: 0.01202 * sqrt(252) * 100 ≈ 19.07
    """
    n = 30
    df = pd.DataFrame({"고가": [101.0] * n, "저가": [99.0] * n})
    val = parkinson_volatility(df, window=30)
    log_hl = math.log(101 / 99)
    expected = math.sqrt((log_hl**2) / (4 * math.log(2))) * math.sqrt(252) * 100
    assert val == pytest.approx(expected, abs=0.05)


# ---------------------------------------------------------------------------
# compute_beta
# ---------------------------------------------------------------------------


def test_beta_double_benchmark(beta_pair_ohlcv):
    """종목 일간수익률이 정확히 벤치의 2배 → beta = 2.0, r_squared = 1.0."""
    stock_df, bench_df = beta_pair_ohlcv
    out = compute_beta(stock_df, bench_df)
    assert out["beta"] == pytest.approx(2.0, abs=0.01)
    assert out["r_squared"] == pytest.approx(1.0, abs=0.01)
    assert out["n"] >= 30


def test_beta_insufficient_data():
    """30행 미만 merged → beta None."""
    stock_df = pd.DataFrame({"종가": np.linspace(100, 110, 20)})
    bench_df = pd.DataFrame({"종가": np.linspace(100, 105, 20)})
    out = compute_beta(stock_df, bench_df)
    assert out["beta"] is None
    assert out["n"] < 30


# ---------------------------------------------------------------------------
# classify_vol_regime
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "realized,expected",
    [
        (None, "unknown"),
        (10.0, "low"),       # < 15
        (14.99, "low"),
        (15.0, "normal"),    # 15 <= x < 25
        (24.99, "normal"),
        (25.0, "high"),      # 25 <= x < 40
        (39.99, "high"),
        (40.0, "extreme"),   # >= 40
        (100.0, "extreme"),
    ],
)
def test_classify_vol_regime_boundaries(realized, expected):
    """경계값 포함 5개 구간 분류 검증."""
    assert classify_vol_regime(realized) == expected
