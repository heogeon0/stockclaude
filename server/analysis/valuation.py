"""
밸류에이션 실구현 — DCF / Reverse DCF / Trading Comps / 확률가중 적정가

LLM의 정성 추정을 대체하는 수치 기반 계산 모듈.

사용 예:
    from server.scrapers.dart import fetch_financials, summarize_financials
    from server.analysis.valuation import forward_dcf, reverse_dcf, probability_weighted_price

    fin = fetch_financials('005930', years=3)
    s = summarize_financials(fin)
    shares = 5_919_637_922  # 삼성전자 상장주식수

    # 1) Forward DCF
    dcf = forward_dcf(s, shares_outstanding=shares, wacc=0.09, terminal_growth=0.025)
    print(f"Forward DCF 적정가: {dcf['적정가']:,}원/주")

    # 2) Reverse DCF
    rev = reverse_dcf(current_price=217250, shares=shares, fin=s, wacc=0.09)
    print(f"현 주가 암시 매출 CAGR: {rev['암시_매출_CAGR']*100:.1f}%")

    # 3) Probability-weighted
    pw = probability_weighted_price(
        {"가격": 260000, "확률": 0.4},  # Bull
        {"가격": 220000, "확률": 0.4},  # Base
        {"가격": 180000, "확률": 0.2},  # Bear
    )
"""

from __future__ import annotations
from typing import Optional
import math


# ============================================================
# v10 — 시장별 WACC 프리셋
# ============================================================

WACC_PRESETS = {
    "kr": {
        "risk_free": 0.035,       # 국고채 10년물 근사
        "wacc": 0.09,             # 대형주 평균
        "terminal_growth": 0.025, # 장기 GDP 성장 근사
        "erp": 0.06,              # Equity Risk Premium
        "tax_rate": 0.22,         # 한국 법인세 최고구간
    },
    "us": {
        "risk_free": 0.042,       # 10Y UST 2026 근사
        "wacc": 0.085,            # S&P 500 대형주 평균
        "terminal_growth": 0.025,
        "erp": 0.05,              # Damodaran 2025 기준
        "tax_rate": 0.21,         # 미국 연방 법인세 최고구간
    },
}


def _preset(market: str = "kr", **overrides) -> dict:
    """시장 프리셋 + override 병합."""
    base = WACC_PRESETS.get(market, WACC_PRESETS["kr"]).copy()
    base.update({k: v for k, v in overrides.items() if v is not None})
    return base


# ============================================================
# Forward DCF — 가정 기반 적정가 산출
# ============================================================

def forward_dcf(
    fin_summary: dict,
    shares_outstanding: int,
    wacc: float = 0.09,
    terminal_growth: float = 0.025,
    projection_years: int = 5,
    revenue_cagr: Optional[float] = None,
    ebit_margin: Optional[float] = None,
    tax_rate: float = 0.22,
    reinvestment_rate: Optional[float] = None,
    market: str = "kr",
) -> dict:
    """
    FCFF 기반 DCF 적정가.

    공식:
        FCFF = EBIT × (1-Tax) × (1 - 재투자율)
        TV = FCFF_마지막년 × (1+g) / (WACC - g)
        EV = ΣFCFF_i / (1+WACC)^i + TV / (1+WACC)^projection_years
        Equity = EV - 순부채 (현금 부족하면 생략)
        적정가 = Equity / 상장주식수

    Args:
        fin_summary: summarize_financials() 결과
        shares_outstanding: 상장주식수 (전체 발행주식)
        wacc: 가중평균자본비용 (기본 9% — 한국 대형주 평균)
        terminal_growth: 영구 성장률 (기본 2.5% — 장기 GDP 성장 근사)
        projection_years: 프로젝션 기간 (기본 5년)
        revenue_cagr: 매출 CAGR 가정. None이면 최근 YoY 사용
        ebit_margin: EBIT 마진 가정. None이면 최근 영업이익률 사용
        tax_rate: 법인세율 (기본 22% — 한국 대기업)
        reinvestment_rate: 재투자율 (Capex+NWC)/영업이익. None이면 매출 성장률의 60%로 추정

    Returns:
        {
            "적정가": int,
            "기업가치_억": int,
            "세부": {"연도별_FCFF": [...], "터미널가치_억": int, ...},
            "가정": {"WACC": float, "g": float, "매출_CAGR": float, "EBIT_마진": float, ...}
        }
    """
    # 시장 프리셋 적용 (US일 때만 기본값 스와프; KR 호출부는 기존 하드코딩 기본값 9%/0.22가 kr 프리셋과 동일해 비회귀)
    if market == "us":
        preset = WACC_PRESETS["us"]
        # 명시적으로 KR 기본값(9%/22%)을 넘긴 호출부는 없음 (분석용 함수로 항상 default 호출)
        # 따라서 default와 같을 때만 US 값으로 덮어쓰기.
        if wacc == 0.09:
            wacc = preset["wacc"]
        if terminal_growth == 0.025:
            terminal_growth = preset["terminal_growth"]
        if tax_rate == 0.22:
            tax_rate = preset["tax_rate"]

    # 가정 해석 (인자 없으면 재무에서 추론)
    if revenue_cagr is None:
        yoy = fin_summary.get("매출_YoY")
        revenue_cagr = (yoy or 5) / 100  # default 5%
    if ebit_margin is None:
        om = fin_summary.get("영업이익률")
        ebit_margin = (om or 10) / 100
    if reinvestment_rate is None:
        # 매출 성장의 60%를 재투자 (통상 가정)
        reinvestment_rate = min(revenue_cagr * 0.6, 0.4)

    # 시작 매출 — 시장별 키 + 단위 분기
    if market == "us":
        revenue_last = (fin_summary.get("매출_M", 0) or 0) * 1e6  # millions USD → USD
    else:
        revenue_last = (fin_summary.get("매출_억", 0) or 0) * 1e8  # 억원 → 원
    if revenue_last <= 0:
        return {"error": "매출 데이터 부족", "적정가": None}

    # 5년 프로젝션
    fcff_list = []
    for year in range(1, projection_years + 1):
        revenue_y = revenue_last * (1 + revenue_cagr) ** year
        ebit_y = revenue_y * ebit_margin
        fcff_y = ebit_y * (1 - tax_rate) * (1 - reinvestment_rate)
        fcff_list.append(fcff_y)

    # 터미널 가치 (Gordon growth)
    if wacc <= terminal_growth:
        return {"error": f"WACC({wacc}) <= g({terminal_growth})", "적정가": None}
    fcff_terminal = fcff_list[-1] * (1 + terminal_growth)
    terminal_value = fcff_terminal / (wacc - terminal_growth)

    # 현재가치 할인
    pv_fcff = sum(f / (1 + wacc) ** (i + 1) for i, f in enumerate(fcff_list))
    pv_terminal = terminal_value / (1 + wacc) ** projection_years
    enterprise_value = pv_fcff + pv_terminal

    # 순부채 차감 (현금 - 부채총계)
    if market == "us":
        cash = (fin_summary.get("현금_M", 0) or 0) * 1e6
    else:
        cash = (fin_summary.get("현금_억", 0) or 0) * 1e8
    # 부채총계가 없으면 equity=EV 근사
    equity_value = enterprise_value + cash  # 단순화: 순현금 가정, 부채 없음이면 + cash / 있으면 별도 처리

    fair_price = int(equity_value / shares_outstanding) if shares_outstanding > 0 else None

    # 단위 — 시장별
    if market == "us":
        scale = 1e6
        scale_suffix = "_M"
    else:
        scale = 1e8
        scale_suffix = "_억"
    return {
        "적정가": fair_price,
        "통화": "USD" if market == "us" else "KRW",
        f"기업가치{scale_suffix}": int(enterprise_value / scale),
        "세부": {
            f"연도별_FCFF{scale_suffix}": [int(f / scale) for f in fcff_list],
            f"터미널가치{scale_suffix}": int(terminal_value / scale),
            f"FCFF_PV{scale_suffix}": int(pv_fcff / scale),
            f"터미널_PV{scale_suffix}": int(pv_terminal / scale),
            f"순현금{scale_suffix}": int(cash / scale),
        },
        "가정": {
            "WACC": wacc,
            "영구성장률": terminal_growth,
            "매출_CAGR": round(revenue_cagr, 4),
            "EBIT_마진": round(ebit_margin, 4),
            "재투자율": round(reinvestment_rate, 4),
            "법인세율": tax_rate,
            "프로젝션_년수": projection_years,
            "시장": market,
        },
    }


# ============================================================
# Reverse DCF — 현 주가를 정당화하는 가정 역산
# ============================================================

def reverse_dcf(
    current_price: float,
    shares: int,
    fin_summary: dict,
    wacc: float = 0.09,
    terminal_growth: float = 0.025,
    projection_years: int = 5,
    ebit_margin: Optional[float] = None,
    tax_rate: float = 0.22,
    market: str = "kr",
) -> dict:
    """
    현 주가를 정당화하는 매출 CAGR 역산.

    접근: EBIT 마진 / 재투자율 / WACC / g는 고정하고, 매출 CAGR만 solve.
    이분법(bisection) 탐색 — [-20%, +60%] 범위에서 forward_dcf 결과가 current_price와 일치하는 CAGR.

    Returns:
        {
            "암시_매출_CAGR": float,       # 현 주가 설명하려면 필요한 CAGR
            "암시_EBIT마진": float,
            "현재가": int,
            "해석": str,                   # "시장은 X% 성장 가정" 같은 서술
            "가정_고정": dict,
        }
    """
    if ebit_margin is None:
        om = fin_summary.get("영업이익률")
        ebit_margin = (om or 10) / 100

    target = current_price

    # 이분법 — CAGR 구간 [-20%, +60%]
    lo, hi = -0.20, 0.60
    best_cagr = None
    for _ in range(50):
        mid = (lo + hi) / 2
        result = forward_dcf(
            fin_summary, shares, wacc, terminal_growth, projection_years,
            revenue_cagr=mid, ebit_margin=ebit_margin, tax_rate=tax_rate,
            market=market,
        )
        fair = result.get("적정가")
        if fair is None:
            return {"error": "DCF 계산 실패", "암시_매출_CAGR": None}
        if abs(fair - target) / target < 0.005:  # 0.5% 이내 수렴
            best_cagr = mid
            break
        if fair < target:
            lo = mid
        else:
            hi = mid
        best_cagr = mid

    interp = _interpret_cagr(best_cagr)

    return {
        "암시_매출_CAGR": round(best_cagr, 4),
        "암시_EBIT마진": round(ebit_margin, 4),
        "현재가": int(current_price),
        "해석": interp,
        "가정_고정": {
            "WACC": wacc,
            "영구성장률": terminal_growth,
            "EBIT_마진": round(ebit_margin, 4),
            "프로젝션_년수": projection_years,
        },
    }


def _interpret_cagr(cagr: float) -> str:
    """CAGR → 정성 해석."""
    if cagr is None:
        return "계산 실패"
    pct = cagr * 100
    if pct < 0:
        return f"시장은 매출 {pct:.1f}% 역성장을 가정 — 이익 방어가 관건"
    if pct < 3:
        return f"시장은 매출 {pct:.1f}% 저성장을 가정 — 현 주가는 디펜시브 수준"
    if pct < 8:
        return f"시장은 매출 {pct:.1f}% 완만 성장을 가정 — 합리적 기대치"
    if pct < 15:
        return f"시장은 매출 {pct:.1f}% 고성장을 가정 — 실적 서프라이즈 없으면 리스크"
    return f"시장은 매출 {pct:.1f}% 초고성장을 가정 — Narrative 극대 베팅 상태"


# ============================================================
# Trading Comps — 비교기업 멀티플 분석
# ============================================================

def trading_comps(target_metrics: dict, peers_metrics: list[dict]) -> dict:
    """
    피어 그룹 대비 밸류에이션 위치.

    Args:
        target_metrics: {"PER": float, "PBR": float, "EV_EBITDA": float} (분석 대상)
        peers_metrics: [{"종목명": str, "PER": float, ...}, ...] (비교기업 리스트)

    Returns:
        {
            "피어_수": int,
            "PER": {"대상": float, "피어_중간값": float, "백분위": int, "프리미엄_할인": str},
            "PBR": {...},
            "EV_EBITDA": {...},
            "종합": "저평가 / 적정 / 고평가",
        }
    """
    import statistics

    if not peers_metrics:
        return {"error": "피어 데이터 없음"}

    result = {"피어_수": len(peers_metrics)}
    verdicts = []

    for metric in ["PER", "PBR", "EV_EBITDA"]:
        peer_vals = [p.get(metric) for p in peers_metrics if p.get(metric) and p[metric] > 0]
        target_val = target_metrics.get(metric)
        if not peer_vals or not target_val or target_val <= 0:
            continue

        median = statistics.median(peer_vals)
        # 백분위 계산 (오름차순 정렬 후 target 위치)
        sorted_peers = sorted(peer_vals)
        below = sum(1 for v in sorted_peers if v < target_val)
        percentile = int(below / len(sorted_peers) * 100)

        premium = (target_val - median) / median * 100
        if premium < -20:
            verdict = "디스카운트"
        elif premium < -5:
            verdict = "소폭 디스카운트"
        elif premium < 5:
            verdict = "피어 부합"
        elif premium < 20:
            verdict = "소폭 프리미엄"
        else:
            verdict = "프리미엄"

        result[metric] = {
            "대상": round(target_val, 1),
            "피어_중간값": round(median, 1),
            "피어_최저": round(min(peer_vals), 1),
            "피어_최고": round(max(peer_vals), 1),
            "백분위": percentile,
            "프리미엄_할인_pct": round(premium, 1),
            "판정": verdict,
        }
        verdicts.append(verdict)

    # 종합 — 3개 지표 중 2개 이상이 디스카운트/프리미엄 쪽이면 종합 판정
    def count(v):
        return sum(1 for x in verdicts if x == v)

    if count("디스카운트") + count("소폭 디스카운트") >= 2:
        result["종합"] = "저평가"
    elif count("프리미엄") + count("소폭 프리미엄") >= 2:
        result["종합"] = "고평가"
    else:
        result["종합"] = "적정"

    return result


# ============================================================
# 확률가중 적정가 (Bull / Base / Bear)
# ============================================================

def probability_weighted_price(bull: dict, base: dict, bear: dict) -> dict:
    """
    Bull/Base/Bear 시나리오 확률가중 평균.

    Args:
        bull: {"가격": int, "확률": float(0~1)}
        base: 동일
        bear: 동일
        확률 합계 = 1.0 (자동 검증)

    Returns:
        {
            "확률가중_적정가": int,
            "시나리오": {...},
            "업사이드_pct": float,  # 현재가 인자 전달 시
            "변동성": int,           # 표준편차
        }
    """
    prob_sum = bull["확률"] + base["확률"] + bear["확률"]
    if abs(prob_sum - 1.0) > 0.01:
        return {"error": f"확률 합계 {prob_sum} ≠ 1.0"}

    weighted = (
        bull["가격"] * bull["확률"]
        + base["가격"] * base["확률"]
        + bear["가격"] * bear["확률"]
    )

    # 표준편차
    mean = weighted
    variance = (
        bull["확률"] * (bull["가격"] - mean) ** 2
        + base["확률"] * (base["가격"] - mean) ** 2
        + bear["확률"] * (bear["가격"] - mean) ** 2
    )
    sigma = math.sqrt(variance)

    return {
        "확률가중_적정가": int(weighted),
        "시나리오": {
            "Bull": bull,
            "Base": base,
            "Bear": bear,
        },
        "변동성_원": int(sigma),
        "변동성_pct": round(sigma / mean * 100, 1) if mean else None,
    }


def upside_from_current(target_price: int, current_price: int) -> dict:
    """적정가 대비 현재가 업사이드/다운사이드."""
    if current_price <= 0:
        return {"error": "현재가 이상"}
    gap = (target_price - current_price) / current_price * 100
    if gap > 30:
        strength = "강한 저평가"
    elif gap > 15:
        strength = "저평가"
    elif gap > -5:
        strength = "적정"
    elif gap > -20:
        strength = "소폭 고평가"
    else:
        strength = "고평가"
    return {
        "업사이드_pct": round(gap, 1),
        "강도": strength,
        "적정가_대비_현재가": round(current_price / target_price, 3),
    }


if __name__ == "__main__":
    import json
    # 삼성전자 샘플 (실제 fetch_financials 결과 형태)
    sample_fin = {
        "매출_억": 3_000_000,   # 300조
        "영업이익_억": 390_000,  # 39조 (영업이익률 13%)
        "순이익_억": 350_000,
        "영업CF_억": 853_151,
        "FCF_억": 377_930,
        "현금_억": 500_000,      # 50조
        "영업이익률": 13.0,
        "순이익률": 11.7,
        "매출_YoY": 10.9,
        "부채비율": 29.9,
    }
    shares_samsung = 5_919_637_922

    print("=== 삼성전자 Forward DCF ===")
    dcf = forward_dcf(sample_fin, shares_samsung, wacc=0.09, terminal_growth=0.025)
    print(json.dumps(dcf, indent=2, ensure_ascii=False))

    print("\n=== 삼성전자 Reverse DCF @ ₩217,250 ===")
    rev = reverse_dcf(217250, shares_samsung, sample_fin, wacc=0.09)
    print(json.dumps(rev, indent=2, ensure_ascii=False))

    print("\n=== 확률가중 적정가 ===")
    pw = probability_weighted_price(
        bull={"가격": 300_000, "확률": 0.35},
        base={"가격": 240_000, "확률": 0.45},
        bear={"가격": 180_000, "확률": 0.20},
    )
    print(json.dumps(pw, indent=2, ensure_ascii=False))
    print("\n업사이드:", upside_from_current(pw["확률가중_적정가"], 217250))
