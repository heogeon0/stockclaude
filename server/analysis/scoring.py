"""
3차원 점수 체계 — 재무 / 산업 / 경제
총점 → 등급 → 액션 템플릿 매핑

- 재무 점수: DART 재무 데이터 기반 자동 계산 (100점)
- 산업 점수: industries/{산업}/base.md 프론트매터 메타데이터 (100점)
- 경제 점수: economy/base.md + economy/{오늘}.md 메타데이터 (100점)

가중 총점 = 재무 × 0.40 + 산업 × 0.35 + 경제 × 0.25

등급:
  85+  Premium    — 손절 -10%, 3단계 피라미딩, 트레일링 스탑(20일선)
  70-84 Standard  — 손절 -8%, 2단계 피라미딩, 기준선 이탈시 관망
  55-69 Cautious  — 손절 -6%, 1단계 피라미딩(돌파 확인 후), 1차 경고 즉시 관망
  <55   Defensive — 손절 -5%, 피라미딩 금지, 기준선 이탈 = 즉시 절반 손절
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional


# ============================================================
# v10 — 시장별 프리셋 (KR 기본값은 기존 로직과 bit-identical)
# ============================================================

# PER/PBR 절대값 임계값 (피어 정보 없을 때 fallback).
# KR: 대형주 중심, PER 8~18 적정. US: 고 Tech PER 정상, PER 15~25 적정.
VALUATION_THRESHOLDS = {
    "kr": {
        "per_bins": [(8, 40), (12, 30), (18, 20), (30, 10)],  # (upper_exclusive, score); else 3
        "pbr_bins": [(0.8, 30), (1.2, 25), (2.0, 18), (4.0, 10)],
    },
    "us": {
        # 대형 Tech 기준 캘리브레이션: PER 15~25 적정, 25~40 약간 고평가(저평가 아님), 40+ 고평가
        "per_bins": [(15, 40), (25, 30), (40, 15), (60, 8)],
        "pbr_bins": [(1.5, 30), (3.0, 20), (6.0, 12), (10.0, 5)],
    },
}

# 재무 요약 키 별칭 (절대 규모 지표만 시장별 분기, 비율은 공통)
FINANCIAL_KEY_ALIASES = {
    "kr": {"영업CF": "영업CF_억", "순이익": "순이익_억", "FCF": "FCF_억", "영업이익": "영업이익_억"},
    "us": {"영업CF": "영업CF_M", "순이익": "순이익_M", "FCF": "FCF_M", "영업이익": "영업이익_M"},
}

# 거시 경제 메타데이터 출처 (v10 참조용; score_macro는 metadata dict만 받음)
MACRO_SOURCES = {
    "kr": "reports/economy/base.md + reports/economy/{YYYY-MM-DD}.md",
    "us": "reports/economy/us-base.md + FRED API (fetch_macro_indicators)",
}


# ============================================================
# 재무 점수 (100점 만점)
# ============================================================

def score_financial(fin_summary: dict, market: str = "kr") -> dict:
    """
    fetch_financials → summarize_financials 결과를 입력받아 0~100점 채점.

    구성요소:
      - 영업이익률  (최대 20점)
      - ROE         (최대 15점)
      - 부채비율    (최대 15점)
      - 영업CF/순이익 (최대 20점) ← 이익 질
      - FCF 양수     (10점)
      - 이익 질 (순이익/영업이익 배율) (10점)
      - 성장성     (10점)

    Returns:
        {"점수": int, "세부": {...}, "등급": str}
    """
    d: dict[str, int] = {}

    # 1. 영업이익률
    om = fin_summary.get("영업이익률")
    if om is None:
        d["영업이익률"] = 0
    elif om > 15:
        d["영업이익률"] = 20
    elif om > 10:
        d["영업이익률"] = 15
    elif om > 5:
        d["영업이익률"] = 10
    else:
        d["영업이익률"] = 5

    # 2. ROE
    roe = fin_summary.get("ROE")
    if roe is None:
        d["ROE"] = 0
    elif roe > 15:
        d["ROE"] = 15
    elif roe > 10:
        d["ROE"] = 10
    else:
        d["ROE"] = 5

    # 3. 부채비율 (낮을수록 좋음)
    dr = fin_summary.get("부채비율")
    if dr is None:
        d["부채비율"] = 0
    elif dr < 50:
        d["부채비율"] = 15
    elif dr < 100:
        d["부채비율"] = 10
    elif dr < 200:
        d["부채비율"] = 5
    else:
        d["부채비율"] = 0

    # 4. 영업CF / 순이익 (이익 질 핵심) — 시장별 키 분기
    _scale = FINANCIAL_KEY_ALIASES.get(market, FINANCIAL_KEY_ALIASES["kr"])
    ocf = fin_summary.get(_scale["영업CF"])
    ni = fin_summary.get(_scale["순이익"])
    if ocf is not None and ni and ni != 0:
        ratio = ocf / ni
        if ratio > 1.0:
            d["이익질"] = 20
        elif ratio > 0.7:
            d["이익질"] = 15
        elif ratio > 0.5:
            d["이익질"] = 10
        else:
            d["이익질"] = 0
    else:
        d["이익질"] = 0

    # 5. FCF 양수
    fcf = fin_summary.get(_scale["FCF"])
    d["FCF양수"] = 10 if (fcf is not None and fcf > 0) else 0

    # 6. 순이익/영업이익 배율 (1배 근접이 정상)
    oi = fin_summary.get(_scale["영업이익"])
    if oi and oi != 0 and ni is not None:
        mult = ni / oi
        if 0.8 <= mult <= 1.2:
            d["이익배율"] = 10
        elif 0.5 <= mult <= 1.5:
            d["이익배율"] = 5
        else:
            d["이익배율"] = 0
    else:
        d["이익배율"] = 0

    # 7. 성장성 (매출 YoY + 영업이익 YoY)
    rev_yoy = fin_summary.get("매출_YoY")
    oi_yoy = fin_summary.get("영업이익_YoY")
    growth = 0
    if rev_yoy is not None and rev_yoy > 0:
        growth += 5
    if oi_yoy is not None and oi_yoy > 0:
        growth += 5
    d["성장성"] = growth

    total = sum(d.values())
    return {"점수": total, "세부": d, "등급": _grade(total, "재무")}


# ============================================================
# 산업 점수 (100점 만점)
# ============================================================

def score_industry(metadata: dict, market: str = "kr") -> dict:
    """
    industries/{산업}/base.md 상단 메타데이터(YAML-like)를 입력받아 채점.

    필수 키 (없으면 0점):
      - 섹터_사이클: "슈퍼사이클" | "회복" | "초입" | "침체"   (최대 30)
      - 성장률_pct: float                                      (최대 20)
      - 경쟁_구도: "과점수혜" | "중립" | "격화"                (최대 15)
      - 규제_환경: "우호" | "중립" | "불리"                    (최대 15)
      - 수요_모멘텀: "강한확대" | "확대" | "유지" | "약화"      (최대 20)
    """
    d: dict[str, int] = {}

    cycle = metadata.get("섹터_사이클", "")
    d["사이클"] = {"슈퍼사이클": 30, "회복": 20, "초입": 10, "침체": 0}.get(cycle, 0)

    g = metadata.get("성장률_pct", 0)
    try:
        g = float(g)
        if g > 10:
            d["성장률"] = 20
        elif g > 5:
            d["성장률"] = 15
        elif g > 0:
            d["성장률"] = 5
        else:
            d["성장률"] = 0
    except (ValueError, TypeError):
        d["성장률"] = 0

    comp = metadata.get("경쟁_구도", "")
    d["경쟁구도"] = {"과점수혜": 15, "중립": 10, "격화": 0}.get(comp, 0)

    reg = metadata.get("규제_환경", "")
    d["규제"] = {"우호": 15, "중립": 10, "불리": 0}.get(reg, 0)

    demand = metadata.get("수요_모멘텀", "")
    d["수요"] = {"강한확대": 20, "확대": 15, "유지": 5, "약화": 0}.get(demand, 0)

    total = sum(d.values())
    return {"점수": total, "세부": d, "등급": _grade(total, "산업")}


# ============================================================
# 경제 점수 (100점 만점)
# ============================================================

def _resolve(metadata: dict, canonical: str, aliases: list[str], score_map: dict[str, int],
             value_aliases: dict[str, str] | None = None) -> int:
    """메타데이터에서 키를 찾아 점수로 변환.

    우선순위:
      1. daily alias 키들을 먼저 확인 — 값이 있으면 그 값 사용
      2. alias 값이 매핑 실패(0점)면 canonical(base) 키로 폴백
      3. 그래도 실패하면 0점

    이렇게 해야 "daily에 임시로 풀네임 쓰다 매핑 실패" 시 base의 안정적 분류가 유지됨.
    """
    def _lookup(raw_value: str) -> int | None:
        raw = str(raw_value).strip()
        if not raw:
            return None
        if value_aliases and raw in value_aliases:
            raw = value_aliases[raw]
        return score_map.get(raw)

    # 1) daily alias 키들
    for alias in aliases:
        val = metadata.get(alias, "")
        if val:
            score = _lookup(val)
            if score is not None:
                return score
            # alias는 있지만 매핑 실패 → 다음 소스로 넘어감

    # 2) canonical (base) 키
    val = metadata.get(canonical, "")
    if val:
        score = _lookup(val)
        if score is not None:
            return score

    # 3) 모두 실패
    return 0


def score_macro(metadata: dict, market: str = "kr") -> dict:
    """
    economy/base.md + 당일 데일리 메타데이터 기반.

    표준 키 (daily에서도 이 키 이름 권장):
      - 금리_환경: "인하"(20) | "동결"(10) | "인상"(0)
      - 환율_수혜: "유리"(15) | "중립"(10) | "불리"(0)
      - 경기_사이클: "확장"(20) | "회복"(15) | "둔화"(5) | "침체"(0)
      - 유동성: "완화"(15) | "중립"(10) | "긴축"(0)
      - 지정학: "안정"(10) | "중립"(5) | "긴장"(0)
      - 외국인_수급: "순매수"(10) | "중립"(5) | "순매도"(0)
      - VI_수준: "낮음"(10) | "중간"(5) | "높음"(0)

    daily 자유 텍스트 허용 별칭:
      - 환율방향 ↔ 환율_수혜, 수급 ↔ 외국인_수급, VI지수 ↔ VI_수준
      - 값 별칭: 약달러/약달러횡보/강달러, 외국인매수/외국인매수전환/외국인매수기조 등
    """
    d: dict[str, int] = {}

    환율_값변환 = {
        "약달러횡보": "중립", "약달러": "유리", "강달러": "불리",
        "원화강세": "유리", "원화약세": "불리", "횡보": "중립",
        "보합": "중립",
    }
    수급_값변환 = {
        "외국인매도": "순매도", "외국인매수": "순매수", "혼조": "중립",
        "외국인순매도": "순매도", "외국인순매수": "순매수",
        "외국인매수전환": "순매수", "외국인매도전환": "순매도",
        "외국인매수기조": "순매수", "외국인매도기조": "순매도",
        "기관매수": "순매수", "기관매도": "순매도",
        "쌍끌이매수": "순매수", "쌍끌이매도": "순매도",
        "쌍매수": "순매수", "쌍매도": "순매도",
    }
    VI_값변환 = {"보통": "중간", "평균": "중간", "안정": "낮음", "경계": "높음"}

    d["금리"] = _resolve(metadata, "금리_환경", [], {"인하": 20, "동결": 10, "인상": 0})
    d["환율"] = _resolve(metadata, "환율_수혜", ["환율방향"], {"유리": 15, "중립": 10, "불리": 0}, 환율_값변환)
    d["경기"] = _resolve(metadata, "경기_사이클", [], {"확장": 20, "회복": 15, "둔화": 5, "침체": 0})
    d["유동성"] = _resolve(metadata, "유동성", [], {"완화": 15, "중립": 10, "긴축": 0})
    d["지정학"] = _resolve(metadata, "지정학", [], {"안정": 10, "중립": 5, "긴장": 0})
    d["수급"] = _resolve(metadata, "외국인_수급", ["수급"], {"순매수": 10, "중립": 5, "순매도": 0}, 수급_값변환)
    d["VI"] = _resolve(metadata, "VI_수준", ["VI지수"], {"낮음": 10, "중간": 5, "높음": 0}, VI_값변환)

    total = sum(d.values())
    return {"점수": total, "세부": d, "등급": _grade(total, "경제")}


# ============================================================
# 밸류에이션 점수 (100점 만점) — PER/PBR/PEG 섹터 백분위
# ============================================================

def score_valuation(fundamentals: dict, peer_metrics: Optional[list[dict]] = None, market: str = "kr") -> dict:
    """
    PER/PBR/PEG 기반 밸류에이션 점수.

    구성:
      - PER 백분위 (최대 40점) — 섹터 피어 대비 낮을수록 고득점
      - PBR 백분위 (최대 30점)
      - PEG (PER / 이익성장률) (최대 30점) — 1 미만이 저평가 기준

    Args:
        fundamentals: fetch_fundamentals() 결과 (PER, PBR, EPS, ...)
        peer_metrics: [{"종목명": str, "PER": float, "PBR": float}, ...] (선택)
                      없으면 PER 절대값 기준 채점

    Returns:
        {"점수": int, "세부": {...}, "등급": str}
    """
    d: dict[str, int] = {}
    per = fundamentals.get("PER")
    pbr = fundamentals.get("PBR")

    # PER 점수
    if per is None or per <= 0:
        d["PER"] = 0
    elif peer_metrics:
        peer_pers = [p.get("PER") for p in peer_metrics if p.get("PER") and p["PER"] > 0]
        if peer_pers:
            below = sum(1 for v in peer_pers if v < per)
            pct = below / len(peer_pers) * 100
            # 백분위 낮을수록(저평가) 점수 높음
            if pct < 25:
                d["PER"] = 40
            elif pct < 50:
                d["PER"] = 30
            elif pct < 75:
                d["PER"] = 15
            else:
                d["PER"] = 5
        else:
            d["PER"] = _per_absolute_score(per, market)
    else:
        d["PER"] = _per_absolute_score(per, market)

    # PBR 점수
    if pbr is None or pbr <= 0:
        d["PBR"] = 0
    elif peer_metrics:
        peer_pbrs = [p.get("PBR") for p in peer_metrics if p.get("PBR") and p["PBR"] > 0]
        if peer_pbrs:
            below = sum(1 for v in peer_pbrs if v < pbr)
            pct = below / len(peer_pbrs) * 100
            if pct < 25:
                d["PBR"] = 30
            elif pct < 50:
                d["PBR"] = 22
            elif pct < 75:
                d["PBR"] = 10
            else:
                d["PBR"] = 3
        else:
            d["PBR"] = _pbr_absolute_score(pbr, market)
    else:
        d["PBR"] = _pbr_absolute_score(pbr, market)

    # PEG 점수
    # 영업이익 or EPS 성장률 필요
    eps = fundamentals.get("EPS")
    eps_growth = fundamentals.get("영업이익_YoY") or fundamentals.get("EPS_YoY")
    if per and per > 0 and eps_growth and eps_growth > 0:
        peg = per / eps_growth
        if peg < 0.5:
            d["PEG"] = 30
        elif peg < 1.0:
            d["PEG"] = 22
        elif peg < 1.5:
            d["PEG"] = 12
        elif peg < 2.5:
            d["PEG"] = 5
        else:
            d["PEG"] = 0
    else:
        d["PEG"] = 0

    total = sum(d.values())
    return {"점수": total, "세부": d, "등급": _grade(total, "밸류")}


def _per_absolute_score(per: float, market: str = "kr") -> int:
    """피어 없을 때 PER 절대값 채점. 시장별 프리셋 (VALUATION_THRESHOLDS) 적용."""
    bins = VALUATION_THRESHOLDS.get(market, VALUATION_THRESHOLDS["kr"])["per_bins"]
    for upper, score in bins:
        if per < upper:
            return score
    return 3


def _pbr_absolute_score(pbr: float, market: str = "kr") -> int:
    """피어 없을 때 PBR 절대값 채점. 시장별 프리셋 적용."""
    bins = VALUATION_THRESHOLDS.get(market, VALUATION_THRESHOLDS["kr"])["pbr_bins"]
    for upper, score in bins:
        if pbr < upper:
            return score
    return 3


# ============================================================
# 기술·수급 점수 (100점 만점) — 단타 등급용
# ============================================================

def score_technical(signals_summary: dict, last_row: dict) -> dict:
    """
    analyze_all → summarize 결과 + 마지막 지표 행을 입력받아 채점.

    구성요소:
      - 시그널 매수 우위     (최대 25점)
      - 추세 정렬 (이평선)   (최대 20점)
      - 모멘텀 (MACD 히스토) (최대 15점)
      - 수급 (거래량 비율)    (최대 15점)
      - RSI 적정 구간        (최대 10점)
      - Stoch 적정 구간      (최대 5점)
      - 일목 삼역호전 여부    (최대 10점)
    """
    d: dict[str, int] = {}

    # 1. 시그널 매수 우위 (가중합 diff 기반, 카운트 fallback)
    buy_w = signals_summary.get("매수_가중합", signals_summary.get("매수", 0))
    sell_w = signals_summary.get("매도_가중합", signals_summary.get("매도", 0))
    diff = buy_w - sell_w
    if diff >= 3.0:
        d["시그널우위"] = 25
    elif diff >= 1.5:
        d["시그널우위"] = 18
    elif diff > -1.5:
        d["시그널우위"] = 10
    elif diff > -3.0:
        d["시그널우위"] = 5
    else:
        d["시그널우위"] = 0

    # 2. 추세 정렬 (이평선 정배열)
    try:
        sma20 = last_row.get("SMA20", 0)
        sma60 = last_row.get("SMA60", 0)
        sma120 = last_row.get("SMA120", 0)
        sma200 = last_row.get("SMA200", 0)
        price = last_row.get("종가", 0)

        aligned = 0
        if price > sma20:
            aligned += 1
        if sma20 > sma60:
            aligned += 1
        if sma60 > sma120:
            aligned += 1
        if sma120 > sma200:
            aligned += 1

        d["추세정렬"] = {4: 20, 3: 15, 2: 10, 1: 5, 0: 0}[aligned]
    except (TypeError, KeyError):
        d["추세정렬"] = 0

    # 3. MACD 모멘텀
    macd_hist = last_row.get("MACD히스토", 0)
    try:
        if macd_hist > 0:
            d["모멘텀"] = 15
        elif macd_hist > -500:
            d["모멘텀"] = 8
        else:
            d["모멘텀"] = 0
    except TypeError:
        d["모멘텀"] = 0

    # 4. 거래량 비율 (수급 에너지)
    vol_ratio = last_row.get("거래량비율", 0)
    try:
        if vol_ratio >= 2.0:
            d["수급에너지"] = 15
        elif vol_ratio >= 1.5:
            d["수급에너지"] = 12
        elif vol_ratio >= 1.0:
            d["수급에너지"] = 8
        else:
            d["수급에너지"] = 3
    except TypeError:
        d["수급에너지"] = 0

    # 5. RSI 적정 구간 (40~70이 단타 최적)
    rsi = last_row.get("RSI14", 50)
    try:
        if 40 <= rsi <= 70:
            d["RSI"] = 10
        elif 30 <= rsi <= 80:
            d["RSI"] = 5
        else:
            d["RSI"] = 0
    except TypeError:
        d["RSI"] = 5

    # 6. Stoch 과매수/과매도 (극단은 감점)
    stoch = last_row.get("Stoch_K", 50)
    try:
        if 20 <= stoch <= 80:
            d["Stoch"] = 5
        else:
            d["Stoch"] = 0  # 과매수/과매도 → 단타 진입 리스크
    except TypeError:
        d["Stoch"] = 3

    # 6b. 극과매수 감점 (RSI>80 or Stoch>90) — 단타 진입 리스크 반영
    try:
        rsi_val = last_row.get("RSI14", 50)
        stoch_val = last_row.get("Stoch_K", 50)
        if rsi_val > 80 or stoch_val > 90:
            d["극과매수_감점"] = -5
        else:
            d["극과매수_감점"] = 0
    except TypeError:
        d["극과매수_감점"] = 0

    # 7. 일목 삼역호전 여부
    try:
        price = last_row.get("종가", 0)
        cloud_top = max(last_row.get("선행스팬A", 0), last_row.get("선행스팬B", 0))
        tenkan = last_row.get("전환선", 0)
        kijun = last_row.get("기준선", 0)

        ichimoku_score = 0
        if price > cloud_top:
            ichimoku_score += 4
        if tenkan > kijun:
            ichimoku_score += 3
        # 후행스팬은 별도 df 필요라 여기선 skip
        d["일목"] = min(ichimoku_score + 3, 10)  # 2/3 충족 시 10점
    except (TypeError, KeyError):
        d["일목"] = 0

    total = sum(d.values())
    return {"점수": total, "세부": d, "등급": _grade(total, "기술")}


# ============================================================
# 타임프레임별 가중치 프리셋
# ============================================================

TIMEFRAME_WEIGHTS = {
    # 단타: 기술 압도적 (밸류에이션 거의 무관)
    "단타": {"재무": 0.10, "산업": 0.15, "경제": 0.15, "기술": 0.55, "밸류에이션": 0.05},
    # 스윙: 재무·산업 우선 + 밸류에이션 반영 (추격매수 방어)
    "스윙": {"재무": 0.30, "산업": 0.25, "경제": 0.20, "기술": 0.05, "밸류에이션": 0.20},
    # 중장기: 재무·밸류 중심 (기술 무시)
    "중장기": {"재무": 0.35, "산업": 0.20, "경제": 0.15, "기술": 0.00, "밸류에이션": 0.30},
    # 모멘텀: 가격 추세 + 상대 강세 중심 (별도 momentum_score 사용 권장)
    "모멘텀": {"재무": 0.15, "산업": 0.25, "경제": 0.15, "기술": 0.40, "밸류에이션": 0.05},
}

# 기본(스윙) 가중치
WEIGHTS = TIMEFRAME_WEIGHTS["스윙"]


def _grade(score: int, label: str) -> str:
    if score >= 85:
        return f"A+ ({label})"
    if score >= 70:
        return f"A ({label})"
    if score >= 55:
        return f"B ({label})"
    if score >= 40:
        return f"C ({label})"
    return f"D ({label})"


def total_grade(financial: dict, industry: dict, macro: dict,
                technical: dict | None = None,
                valuation: dict | None = None,
                timeframe: str = "스윙") -> dict:
    """
    가중 총점 산출 + 등급 + 액션 템플릿.

    Args:
        timeframe: "단타" | "스윙" (기본) | "중장기" | "모멘텀"
        technical: score_technical() 결과 (단타/모멘텀일 때 필수)
        valuation: score_valuation() 결과 (스윙/중장기 권장)
    """
    w = TIMEFRAME_WEIGHTS.get(timeframe, TIMEFRAME_WEIGHTS["스윙"])

    total = round(
        financial["점수"] * w.get("재무", 0)
        + industry["점수"] * w.get("산업", 0)
        + macro["점수"] * w.get("경제", 0)
        + (technical["점수"] if technical else 0) * w.get("기술", 0)
        + (valuation["점수"] if valuation else 0) * w.get("밸류에이션", 0),
        1,
    )

    if timeframe == "단타":
        tier, action = _tier_daytrade(total)
    else:
        tier, action = _tier(total)

    result = {
        "가중총점": total,
        "등급": tier,
        "타임프레임": timeframe,
        "액션_템플릿": action,
        "내역": {
            "재무": financial,
            "산업": industry,
            "경제": macro,
        },
    }
    if technical:
        result["내역"]["기술"] = technical
    if valuation:
        result["내역"]["밸류에이션"] = valuation
    return result


def _tier_daytrade(total: float) -> tuple[str, dict]:
    """
    단타 전용 등급 + 액션.

    단타 = 기술 기반 스윙 (2일~4주). 시간 기반이 아닌 **기술 시그널 기반 청산**.
    청산 조건: 기준선/이평선/52주 레벨 이탈, 삼역호전 해제, 모멘텀 반전.
    """
    if total >= 85:
        return "Premium-단타", {
            "손절폭": "-3% or ATR 1.5배 (타이트 but 충분한 숨구멍)",
            "피라미딩": "4단계 분할 (돌파/+2%/+5%/+8% 각 1/4)",
            "홀딩_기준": "전환선/20일선 이탈 시까지 유지 — 시간 제한 없음 (2일~4주)",
            "트레일링": "전환선 종가 기준",
            "익절": "목표가 도달 시 1/2 부분익절, 잔여는 트레일링 유지",
            "메모": "추세+수급+기술 모두 A급. 공격적 추세 추종",
        }
    if total >= 70:
        return "Standard-단타", {
            "손절폭": "-4% or ATR 2배",
            "피라미딩": "3단계 분할 (돌파/+3%/+6%)",
            "홀딩_기준": "기준선 이탈 시 청산 — 시간 제한 없음 (2일~4주)",
            "트레일링": "기준선 or 20일선 (둘 중 가까운 쪽)",
            "익절": "+8~12% 도달 시 1/3 부분익절, 잔여 유지",
            "메모": "기술적 우위 확인. 분할 매수 + 추세 따라가기",
        }
    if total >= 55:
        return "Cautious-단타", {
            "손절폭": "-3% (타이트)",
            "피라미딩": "2단계 분할 (52주 고가 돌파 + 거래량 2배 확인 시 / +5% 도달 시)",
            "홀딩_기준": "기준선 이탈 or 추세 반전 시그널 발생 시 청산",
            "트레일링": "기준선",
            "익절": "+5~8% 도달 시 즉시 부분 익절, 잔여는 기술 시그널 유지 동안 홀딩",
            "메모": "펀더멘털 약함 but 기술 단서 있음. 돌파 확인 후 2단계 분할 진입",
        }
    return "Defensive-단타", {
        "손절폭": "-2% (극타이트)",
        "피라미딩": "1단계만 (강한 돌파 + 거래량 3배 확인 시)",
        "홀딩_기준": "1차 경고 즉시 전량 청산",
        "트레일링": "전환선 (타이트)",
        "익절": "+3~5% 즉시 전량",
        "메모": "기술·수급 약함. 진입 소량, 타이트 관리. 실패 시 즉시 손절",
    }


def _tier(total: float) -> tuple[str, dict]:
    if total >= 85:
        return "Premium", {
            "손절폭": "-10% 또는 200일선",
            "피라미딩": "3단계 분할 (돌파가/+5%/+10% 각 1/3)",
            "홀딩_방식": "트레일링 스탑 (20일선 이탈)",
            "익절": "컨센서스 상단까지 홀딩 + 부분 익절",
            "메모": "재무/산업/경제 모두 견고 — 방어적 홀딩 + 업사이드 최대화",
        }
    if total >= 70:
        return "Standard", {
            "손절폭": "-8% (미너비니 기본)",
            "피라미딩": "2단계 분할 (돌파가/+5% 각 1/2)",
            "홀딩_방식": "기준선(일목) 이탈 시 관망",
            "익절": "목표가 도달 시 1/3 부분익절",
            "메모": "표준 추세추종. 원칙적 손절 + 분할 매수",
        }
    if total >= 55:
        return "Cautious", {
            "손절폭": "-6% (타이트)",
            "피라미딩": "1단계만 (52주 고가 돌파 + 거래량 확인 후)",
            "홀딩_방식": "1차 경고 발생 시 즉시 관망 모드",
            "익절": "목표가 대비 -10% 구간에서 적극 익절",
            "메모": "일부 리스크 존재. 보수적 진입 + 빠른 이익실현",
        }
    return "Defensive", {
        "손절폭": "-5% (매우 타이트)",
        "피라미딩": "금지",
        "홀딩_방식": "기준선 이탈 = 즉시 절반 손절",
        "익절": "조기 익절 권장. 단기 트레이딩만",
        "메모": "구조적 리스크 존재. 진입 자제 or 단타만. 장기 홀딩 비권장",
    }


# ============================================================
# 메타데이터 로더 (YAML frontmatter 파싱)
# ============================================================

def load_metadata(md_path: Path | str) -> dict:
    """
    마크다운 파일 상단의 YAML frontmatter를 dict로 반환.

    형식:
    ---
    key: value
    ---
    ...
    """
    path = Path(md_path)
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}

    end = text.find("---", 3)
    if end == -1:
        return {}

    block = text[3:end].strip()
    result = {}
    for raw in block.split("\n"):
        line = raw.split("#", 1)[0].rstrip()   # 전체 주석 + 인라인 주석 제거
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if not k or not v:
            continue
        # 숫자 파싱
        try:
            v = float(v) if "." in v else int(v)
        except ValueError:
            pass
        result[k] = v
    return result


# ============================================================
# 통합 호출 헬퍼
# ============================================================

def score_consensus(consensus: dict, current_price: float) -> dict:
    """
    애널리스트 컨센서스 기반 점수 (참고용, 가중 총점에는 미반영).

    Args:
        consensus: aggregate_consensus() 결과
        current_price: 현재 종가

    Returns:
        {"목표가_괴리율": float, "의견_강도": str, "컨센서스": dict}
    """
    result = {"컨센서스": consensus}

    avg = consensus.get("목표가_평균")
    if avg and current_price > 0:
        gap = (avg - current_price) / current_price * 100
        result["목표가_괴리율"] = round(gap, 1)
        if gap > 30:
            result["의견_강도"] = "강한 저평가"
        elif gap > 15:
            result["의견_강도"] = "저평가"
        elif gap > 0:
            result["의견_강도"] = "소폭 저평가"
        elif gap > -15:
            result["의견_강도"] = "적정~소폭 고평가"
        else:
            result["의견_강도"] = "고평가"
    else:
        result["목표가_괴리율"] = None
        result["의견_강도"] = "데이터 부족"

    opinions = consensus.get("투자의견_분포", {})
    total = sum(opinions.values()) if opinions else 0
    buy_pct = opinions.get("Buy", 0) / total * 100 if total > 0 else 0
    result["매수의견_비율"] = round(buy_pct, 1)

    return result


def grade_stock(fin_summary: dict, industry_md_path: str | Path, economy_md_path: str | Path,
                economy_daily_path: str | Path | None = None,
                timeframe: str = "스윙",
                signals_summary: dict | None = None,
                last_row: dict | None = None,
                consensus: dict | None = None,
                current_price: float = 0,
                fundamentals: dict | None = None,
                peer_metrics: list[dict] | None = None,
                market: str = "kr") -> dict:
    """
    fin_summary (DART 기반) + industry/economy 메타데이터 → 종합 등급.

    Args:
        fin_summary: summarize_financials() 결과
        industry_md_path: industries/{산업}/base.md
        economy_md_path: economy/base.md
        economy_daily_path: economy/YYYY-MM-DD.md (선택)
        timeframe: "단타" | "스윙" (기본) | "중장기" | "모멘텀"
        signals_summary: summarize(analyze_all(df)) 결과 (단타/모멘텀일 때 필수)
        last_row: df.iloc[-1].to_dict() (단타/모멘텀일 때 필수)
        consensus: aggregate_consensus() 결과 (선택)
        current_price: 현재 종가 (consensus와 함께 사용)
        fundamentals: naver_finance.fetch_fundamentals() 결과 (밸류에이션 점수용)
        peer_metrics: 피어 그룹 [{"PER":..., "PBR":...}, ...] (선택, 섹터 백분위용)

    Returns:
        total_grade() 결과 + 컨센서스 정보
    """
    fin = score_financial(fin_summary, market=market)
    ind = score_industry(load_metadata(industry_md_path), market=market)
    macro_meta = load_metadata(economy_md_path)
    if economy_daily_path:
        macro_meta.update(load_metadata(economy_daily_path))
    macro = score_macro(macro_meta, market=market)

    tech = None
    if timeframe in ("단타", "모멘텀") and signals_summary and last_row:
        tech = score_technical(signals_summary, last_row)

    val = None
    if fundamentals:
        val = score_valuation(fundamentals, peer_metrics, market=market)

    result = total_grade(fin, ind, macro, technical=tech, valuation=val, timeframe=timeframe)

    if consensus and consensus.get("리포트수", 0) > 0:
        result["컨센서스"] = score_consensus(consensus, current_price)

    return result


if __name__ == "__main__":
    import json
    # 테스트 데이터 (삼성전자 재무)
    sample = {
        "영업이익률": 13.1, "순이익률": 13.6, "ROE": 10.4, "ROA": 8.0,
        "부채비율": 29.9, "유동비율": 232.8, "영업CF_억": 853151,
        "FCF_억": 377930, "순이익_억": 452068, "영업이익_억": 436011,
        "매출_YoY": 10.9, "영업이익_YoY": 33.2,
    }
    print("=== 삼성전자 재무 채점 ===")
    print(json.dumps(score_financial(sample), indent=2, ensure_ascii=False))
