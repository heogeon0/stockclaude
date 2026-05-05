"""server.analysis.financials 유닛 테스트.

순수 함수 — 입력은 dict/scalar, 출력은 dict/str/int. DB 의존 X.
손계산 가능한 작은 입력으로 정확값 검증.
"""
from __future__ import annotations

import pytest

from server.analysis.financials import (
    analyze_trend,
    compute_financial_ratios,
    compute_financial_score,
    compute_growth_rates,
    detect_earnings_surprise,
)


# ---------------------------------------------------------------------------
# compute_financial_ratios
# ---------------------------------------------------------------------------


def test_ratios_per_pbr_passthrough():
    """PER/PBR이 직접 주어지면 그대로 보존."""
    out = compute_financial_ratios(per=12.5, pbr=1.8, eps=1000.0, bps=8000.0)
    assert out["per"] == 12.5
    assert out["pbr"] == 1.8


def test_ratios_per_computed_when_missing():
    """price/eps 로 PER 자동 계산 (per 누락 시)."""
    out = compute_financial_ratios(price=78000.0, eps=6000.0)
    assert out["per"] == 13.0  # 78000 / 6000
    assert out["pbr"] is None  # bps 없음


def test_ratios_pbr_computed_when_missing():
    """price/bps 로 PBR 자동 계산."""
    out = compute_financial_ratios(price=78000.0, bps=39000.0)
    assert out["pbr"] == 2.0


def test_ratios_eps_zero_skips_per_division():
    """eps=0 일 때 0 division 회피 → per None 유지."""
    out = compute_financial_ratios(price=78000.0, eps=0.0)
    assert out["per"] is None


def test_ratios_margins_and_roe():
    """매출·이익·자본 → 마진율/ROE/ROA 계산.

    revenue=1000, op_profit=200, net_profit=100, total_equity=500, total_assets=1000
    → op_margin=20%, net_margin=10%, roe=20%, roa=10%
    """
    out = compute_financial_ratios(
        revenue=1000.0, op_profit=200.0, net_profit=100.0,
        total_equity=500.0, total_assets=1000.0,
    )
    assert out["op_margin"] == 20.0
    assert out["net_margin"] == 10.0
    assert out["roe"] == 20.0
    assert out["roa"] == 10.0


def test_ratios_debt_ratio_and_fcf_yield():
    """부채비율 + FCF yield 계산.

    total_debt=300, total_equity=500 → debt_ratio = 60%
    fcf=50, price=10, shares_outstanding=100 → market_cap=1000, fcf_yield = 5%
    """
    out = compute_financial_ratios(
        total_debt=300.0, total_equity=500.0,
        fcf=50.0, price=10.0, shares_outstanding=100.0,
    )
    assert out["debt_ratio"] == 60.0
    assert out["fcf_yield"] == 5.0


def test_ratios_all_none_when_no_inputs():
    """입력 전부 None → 계산되는 비율은 모두 None (로직 안전)."""
    out = compute_financial_ratios()
    derived = ["psr", "ev_ebitda", "roe", "roa", "op_margin",
               "net_margin", "debt_ratio", "fcf_yield"]
    assert all(out[k] is None for k in derived)


# ---------------------------------------------------------------------------
# compute_growth_rates
# ---------------------------------------------------------------------------


def test_growth_insufficient_data():
    """1분기만 있으면 모든 성장률 None."""
    out = compute_growth_rates([{"revenue": 100, "op_profit": 20, "eps": 5}])
    assert all(v is None for v in out.values())


def test_growth_qoq_only_when_no_year_old():
    """2~4분기만 있으면 QoQ 만, YoY None."""
    quarterly = [
        {"revenue": 100, "op_profit": 20},
        {"revenue": 110, "op_profit": 24},  # 최신
    ]
    out = compute_growth_rates(quarterly)
    assert out["revenue_qoq"] == 10.0   # (110-100)/100 * 100
    assert out["op_profit_qoq"] == 20.0  # (24-20)/20 * 100
    assert out["revenue_yoy"] is None
    assert out["op_profit_yoy"] is None


def test_growth_yoy_with_5_quarters():
    """5분기 이상 → YoY 계산. quarterly[-5] 가 1년 전."""
    quarterly = [
        {"revenue": 100, "op_profit": 20, "net_profit": 10, "eps": 5},  # -5: 1년 전
        {"revenue": 105, "op_profit": 21, "net_profit": 11, "eps": 5.2},
        {"revenue": 110, "op_profit": 22, "net_profit": 12, "eps": 5.4},
        {"revenue": 115, "op_profit": 23, "net_profit": 13, "eps": 5.6},
        {"revenue": 130, "op_profit": 30, "net_profit": 18, "eps": 7.0},  # 최신 (-1)
    ]
    out = compute_growth_rates(quarterly)
    assert out["revenue_yoy"] == 30.0          # (130-100)/100 *100
    assert out["op_profit_yoy"] == 50.0        # (30-20)/20 *100
    assert out["net_profit_yoy"] == 80.0       # (18-10)/10 *100
    assert out["eps_yoy"] == 40.0              # (7-5)/5 *100
    # QoQ는 가장 마지막 직전 분기 대비
    assert out["revenue_qoq"] == pytest.approx(13.04, abs=0.01)


def test_growth_zero_division_safe():
    """이전 값 0 → None (division 회피)."""
    quarterly = [{"revenue": 0}, {"revenue": 100}]
    out = compute_growth_rates(quarterly)
    assert out["revenue_qoq"] is None


# ---------------------------------------------------------------------------
# detect_earnings_surprise
# ---------------------------------------------------------------------------


def test_surprise_consensus_zero_returns_inline():
    """0 division 회피: consensus=0 → inline / weak."""
    out = detect_earnings_surprise(actual=100, consensus=0)
    assert out["verdict"] == "inline"
    assert out["magnitude"] == "weak"
    assert out["surprise_pct"] is None


def test_surprise_inline_within_3pct():
    """|surprise| < 3% → inline / weak."""
    out = detect_earnings_surprise(actual=102, consensus=100)  # +2%
    assert out["verdict"] == "inline"
    assert out["magnitude"] == "weak"
    assert out["surprise_pct"] == 2.0


def test_surprise_beat_mild_without_std_error():
    """+5% (3<x≤10), std_error 없음 → beat / mild."""
    out = detect_earnings_surprise(actual=105, consensus=100)
    assert out["verdict"] == "beat"
    assert out["magnitude"] == "mild"
    assert out["surprise_pct"] == 5.0


def test_surprise_beat_strong_above_10pct():
    """+15% (>10%), std_error 없음 → beat / strong (pct 폴백)."""
    out = detect_earnings_surprise(actual=115, consensus=100)
    assert out["verdict"] == "beat"
    assert out["magnitude"] == "strong"


def test_surprise_miss_mild():
    """-5% → miss / mild."""
    out = detect_earnings_surprise(actual=95, consensus=100)
    assert out["verdict"] == "miss"
    assert out["magnitude"] == "mild"
    assert out["surprise_pct"] == -5.0


def test_surprise_strong_via_z_score():
    """std_error 제공 시 z-score 기반 magnitude. (actual-consensus)/std_error = 2.0 > 1.5 → strong."""
    out = detect_earnings_surprise(actual=110, consensus=100, std_error=5)
    # surprise_pct = 10% (3 < 10, beat 분기 진입)
    # z = (110-100)/5 = 2.0 > 1.5 → strong
    assert out["verdict"] == "beat"
    assert out["magnitude"] == "strong"


# ---------------------------------------------------------------------------
# analyze_trend
# ---------------------------------------------------------------------------


def test_trend_insufficient_data_is_flat():
    """3 미만 데이터 → flat."""
    assert analyze_trend([100.0, 110.0]) == "flat"
    assert analyze_trend([]) == "flat"


def test_trend_improving_strong_uptrend():
    """선형 증가 시리즈 → improving (slope/y_mean > 0.02)."""
    assert analyze_trend([100.0, 110.0, 120.0, 130.0, 140.0]) == "improving"


def test_trend_deteriorating_strong_downtrend():
    """선형 감소 시리즈 → deteriorating."""
    assert analyze_trend([140.0, 130.0, 120.0, 110.0, 100.0]) == "deteriorating"


def test_trend_flat_oscillating():
    """진동 (평균 근처 ±1%) → flat."""
    assert analyze_trend([100.0, 101.0, 99.0, 100.5, 99.5]) == "flat"


def test_trend_skips_none_in_input():
    """None 값은 필터되고 나머지로 판정. [100, None, 120, 140] → [100, 120, 140] → improving."""
    assert analyze_trend([100.0, None, 120.0, 140.0]) == "improving"  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# compute_financial_score (clamp + 중립 기준만 검증 — 가중치 튜닝은 별도 백테스트)
# ---------------------------------------------------------------------------


def test_financial_score_neutral_baseline():
    """입력 모두 None → 중립 50."""
    assert compute_financial_score(ratios={"roe": None, "op_margin": None,
                                           "debt_ratio": None, "fcf_yield": None}) == 50


def test_financial_score_clamped_to_0_100():
    """극단 음수 입력에서도 0 미만으로 안 떨어짐."""
    out = compute_financial_score(
        ratios={"roe": -100, "op_margin": -100, "debt_ratio": 500, "fcf_yield": -50},
        growth={"revenue_yoy": -50, "op_profit_yoy": -100},
    )
    assert 0 <= out <= 100


def test_financial_score_high_quality_stack():
    """우수 펀더멘털 (ROE 25, op_margin 35, debt_ratio 30, fcf_yield 7) → 70 이상."""
    out = compute_financial_score(
        ratios={"roe": 25, "op_margin": 35, "debt_ratio": 30, "fcf_yield": 7},
        growth={"revenue_yoy": 35, "op_profit_yoy": 60},
    )
    assert out >= 80
    assert out <= 100  # clamp 확인
