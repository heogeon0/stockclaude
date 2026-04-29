"""
전략별 매매 시그널 판단
- 각 함수는 indicators.compute_all() 결과를 입력받아
  {전략명, 시그널, 조건, 진입가, 손절가, 설명} 반환
- 시그널: "매수" / "매도" / "관망"
"""

import pandas as pd
from .indicators import detect_vcp

# 전략별 기본 가중치 (백테스트 캐시 없을 때 fallback)
STRATEGY_WEIGHTS = {
    # 추세 추종
    "일목균형표": 2.0,
    "미너비니 SEPA": 1.5,
    "래리윌리엄스": 1.0,
    "리버모어 피봇": 1.0,
    "TripleScreen": 1.0,
    "볼린저": 1.0,
    "그랜빌(SMA20)": 0.5,
    "그랜빌(SMA60)": 0.5,
    "그랜빌(SMA120)": 0.5,
    # 역추세/매도 (과열 방어 — 가중치 보수적)
    "RSI과열": 1.5,
    "평균회귀": 1.0,
    "추세반전": 2.0,
}


def weights_from_backtest(backtest_result: dict) -> dict[str, float]:
    """
    백테스트 승률 기반으로 종목별 가중치 생성.
    승률 60%+ → 가중치 상향, 50% 미만 → 하향, 샘플 5회 미만 → 기본값.

    Args:
        backtest_result: backtest_stock() 또는 load_cache() 결과

    Returns:
        전략명 → 가중치 dict
    """
    if not backtest_result or "전략별" not in backtest_result:
        return STRATEGY_WEIGHTS.copy()

    weights = {}
    strats = backtest_result["전략별"]

    for name, base_w in STRATEGY_WEIGHTS.items():
        data = strats.get(name)
        if not data or data["총_시그널"] < 5:
            weights[name] = base_w
            continue

        wr = data.get("5일_승률", 50)

        # 승률 기반 스케일링: 50%=1.0x, 70%=1.5x, 40%=0.7x
        scale = 0.5 + (wr / 100)  # 30%→0.8, 50%→1.0, 70%→1.2, 90%→1.4
        adjusted = round(base_w * scale, 1)

        # 클램핑: 최소 0.2, 최대 3.0
        weights[name] = max(0.2, min(3.0, adjusted))

    return weights


def _atr_stop(price: float, atr_value: float, direction: str = "long", multiplier: float = 2.0) -> float:
    """
    ATR 기반 손절가 계산.
    long  → price - (ATR × multiplier)
    short → price + (ATR × multiplier)
    """
    if pd.isna(atr_value):
        # ATR 없을 때 fallback: 7% 고정
        return price * 0.93 if direction == "long" else price * 1.07
    offset = atr_value * multiplier
    return price - offset if direction == "long" else price + offset


# ============================================================
# 1. 일목균형표
# ============================================================

def ichimoku_signal(df: pd.DataFrame) -> dict:
    """
    일목균형표 — 삼역호전/역전, 구름대 돌파 판단.
    """
    last = df.iloc[-1]
    price = last["종가"]

    # 구름대 상단/하단
    cloud_top = max(last["선행스팬A"], last["선행스팬B"])
    cloud_bot = min(last["선행스팬A"], last["선행스팬B"])

    above_cloud = price > cloud_top
    below_cloud = price < cloud_bot
    tenkan_above = last["전환선"] > last["기준선"]

    # 후행스팬 vs 26일 전 가격
    chikou_above = False
    if len(df) >= 27:
        chikou_above = df.iloc[-27]["종가"] < price

    # 삼역호전
    if above_cloud and tenkan_above and chikou_above:
        signal = "매수"
        condition = "삼역호전 (구름대 위 + 전환선>기준선 + 후행스팬 위)"
        stop_loss = last["기준선"]
    elif below_cloud and not tenkan_above and not chikou_above:
        signal = "매도"
        condition = "삼역역전 (구름대 아래 + 전환선<기준선 + 후행스팬 아래)"
        stop_loss = last["기준선"]
    elif above_cloud and tenkan_above:
        signal = "매수"
        condition = "구름대 위 + 전환선/기준선 호전"
        stop_loss = cloud_bot
    else:
        signal = "관망"
        condition = f"구름대 {'위' if above_cloud else '아래' if below_cloud else '내부'}, 방향성 불명확"
        stop_loss = None

    return {
        "전략": "일목균형표",
        "시그널": signal,
        "조건": condition,
        "진입가": price if signal == "매수" else None,
        "손절가": round(stop_loss) if stop_loss else None,
    }


# ============================================================
# 2. 래리 윌리엄스 변동성 돌파
# ============================================================

def larry_williams_signal(df: pd.DataFrame, k: float = 0.5) -> dict:
    """
    래리 윌리엄스 — 당일 시가 + (전일 Range × k) 돌파 판단.
    """
    last = df.iloc[-1]
    breakout_price = last[f"돌파가_k{k}"]
    prev_range = df.iloc[-2]["고가"] - df.iloc[-2]["저가"]

    if pd.isna(breakout_price):
        return {"전략": "래리윌리엄스", "시그널": "관망", "조건": "데이터 부족"}

    if last["고가"] >= breakout_price:
        signal = "매수"
        condition = f"돌파가 {breakout_price:,.0f} 돌파 성공 (고가 {last['고가']:,.0f})"
        stop_loss = breakout_price - prev_range * 2
    else:
        signal = "관망"
        condition = f"돌파가 {breakout_price:,.0f} 미돌파 (현재 {last['종가']:,.0f})"
        stop_loss = None

    return {
        "전략": "래리윌리엄스",
        "시그널": signal,
        "조건": condition,
        "진입가": round(breakout_price),
        "손절가": round(stop_loss) if stop_loss else None,
    }


# ============================================================
# 3. 마크 미너비니 SEPA (트렌드 템플릿 + VCP)
# ============================================================

def minervini_signal(df: pd.DataFrame) -> dict:
    """
    미너비니 SEPA — 트렌드 템플릿 8조건 + VCP 패턴.
    (RS Rating, 펀더멘털은 외부 데이터 필요 — 여기선 기술 조건만)
    """
    last = df.iloc[-1]
    price = last["종가"]

    # 트렌드 템플릿 기술 조건 (1~4)
    cond_1 = price > last["SMA50"] > last["SMA150"] > last["SMA200"]
    cond_2 = last["SMA200"] > df.iloc[-22]["SMA200"] if len(df) >= 22 else False
    cond_3 = last["고가대비%"] >= 75  # 52주 고가 75% 이상
    cond_4 = last["저가대비%"] >= 125  # 52주 저가 125% 이상

    conditions_met = sum([cond_1, cond_2, cond_3, cond_4])

    vcp = detect_vcp(df)

    if conditions_met == 4 and vcp["is_vcp"]:
        signal = "매수"
        condition = f"트렌드 템플릿 4조건 충족 + VCP 패턴 감지 (수축: {vcp['contractions']})"
        # ATR 기반 손절 (미너비니 7~8% 룰의 변동성 반영 버전)
        stop_loss = _atr_stop(price, last.get("ATR14"), "long", multiplier=2.5)
    elif conditions_met == 4:
        signal = "관망"
        condition = f"트렌드 템플릿 충족이나 VCP 대기 (수축: {vcp['contractions']})"
        stop_loss = None
    else:
        signal = "관망"
        condition = f"트렌드 템플릿 {conditions_met}/4 조건 충족"
        stop_loss = None

    return {
        "전략": "미너비니 SEPA",
        "시그널": signal,
        "조건": condition,
        "진입가": price if signal == "매수" else None,
        "손절가": round(stop_loss) if stop_loss else None,
        "부가정보": {
            "조건1_이평정렬": cond_1,
            "조건2_200MA상승": cond_2,
            "조건3_52주고가75%": cond_3,
            "조건4_52주저가125%": cond_4,
            "VCP": vcp,
        }
    }


# ============================================================
# 4. 제시 리버모어 피봇 포인트
# ============================================================

def livermore_signal(df: pd.DataFrame, consolidation_days: int = 20) -> dict:
    """
    리버모어 — 장기 횡보 후 피봇 포인트 돌파 + 거래량 증가.
    """
    last = df.iloc[-1]

    # 최근 N일 고가를 피봇 포인트로 간주
    recent = df.tail(consolidation_days)
    pivot = recent["고가"].max()

    # 횡보 판단: 최근 N일 레인지가 평균 종가의 10% 이내
    price_range = (recent["고가"].max() - recent["저가"].min()) / recent["종가"].mean()
    is_consolidating = price_range < 0.10

    # 거래량 증가 확인
    vol_surge = last["거래량비율"] > 1.5 if not pd.isna(last["거래량비율"]) else False

    # 돌파 확인
    is_breakout = last["종가"] > pivot

    if is_consolidating and is_breakout and vol_surge:
        signal = "매수"
        condition = f"횡보 후 피봇 {pivot:,.0f} 돌파 + 거래량 {last['거래량비율']:.1f}배"
        stop_loss = pivot * 0.97
    elif is_breakout and vol_surge:
        signal = "매수"
        condition = f"피봇 {pivot:,.0f} 돌파 + 거래량 증가 (횡보 조건 미충족)"
        stop_loss = pivot * 0.97
    else:
        signal = "관망"
        reason = []
        if not is_consolidating:
            reason.append("횡보 아님")
        if not is_breakout:
            reason.append(f"피봇 {pivot:,.0f} 미돌파")
        if not vol_surge:
            reason.append("거래량 부족")
        condition = ", ".join(reason)
        stop_loss = None

    return {
        "전략": "리버모어 피봇",
        "시그널": signal,
        "조건": condition,
        "진입가": round(pivot) if signal == "매수" else None,
        "손절가": round(stop_loss) if stop_loss else None,
    }


# ============================================================
# 5. 알렉산더 엘더 Triple Screen
# ============================================================

def triple_screen_signal(df: pd.DataFrame) -> dict:
    """
    엘더 Triple Screen — 주봉 MACD + 일봉 오실레이터 + 4시간봉 진입.
    일봉 기준으로 간소화: MACD 히스토그램(추세) + 스토캐스틱(과매도/과매수).
    """
    if len(df) < 50:
        return {"전략": "TripleScreen", "시그널": "관망", "조건": "데이터 부족"}

    last = df.iloc[-1]

    # 1차 스크린: MACD 히스토그램 방향 (추세)
    macd_hist = last["MACD히스토"]
    macd_hist_prev = df.iloc[-2]["MACD히스토"]
    trend_up = macd_hist > 0
    trend_accel = macd_hist > macd_hist_prev
    trend_down = macd_hist < 0
    trend_decel = macd_hist < macd_hist_prev

    # 2차 스크린: 스토캐스틱 (조정 구간 감지)
    stoch_k = last["Stoch_K"]
    stoch_pullback = stoch_k < 50  # 상승 추세 중 조정 = Stoch 50 이하
    stoch_oversold = stoch_k < 20
    stoch_overbought = stoch_k > 80
    stoch_rally = stoch_k > 50  # 하락 추세 중 반등 = Stoch 50 이상

    # 상승 추세 + 조정 구간 → 매수 (원전: 추세 중 눌림 매수)
    if trend_up and stoch_oversold:
        signal = "매수"
        condition = f"상승추세(MACD↑) + 과매도(Stoch {stoch_k:.0f}) — 강한 매수"
        stop_loss = last["저가"] * 0.98
    elif trend_up and trend_accel and stoch_pullback:
        signal = "매수"
        condition = f"상승추세(MACD↑가속) + 조정(Stoch {stoch_k:.0f}<50) — 눌림 매수"
        stop_loss = last["저가"] * 0.98
    elif trend_down and stoch_overbought:
        signal = "매도"
        condition = f"하락추세(MACD↓) + 과매수(Stoch {stoch_k:.0f})"
        stop_loss = last["고가"] * 1.02
    elif trend_down and trend_decel and stoch_rally:
        signal = "매도"
        condition = f"하락추세(MACD↓감속) + 반등(Stoch {stoch_k:.0f}>50) — 반등 매도"
        stop_loss = last["고가"] * 1.02
    else:
        signal = "관망"
        if trend_up and stoch_k > 50:
            condition = f"추세↑이나 과매수(Stoch {stoch_k:.0f}) — 눌림 대기"
        elif trend_down and stoch_k < 50:
            condition = f"추세↓이나 과매도(Stoch {stoch_k:.0f}) — 반등 대기"
        else:
            condition = f"MACD히스토 {macd_hist:.1f}, Stoch {stoch_k:.0f}"
        stop_loss = None

    return {
        "전략": "TripleScreen",
        "시그널": signal,
        "조건": condition,
        "진입가": last["종가"] if signal in ["매수", "매도"] else None,
        "손절가": round(stop_loss) if stop_loss else None,
    }


# ============================================================
# 6. 볼린저밴드 스퀴즈/브레이크아웃
# ============================================================

def bollinger_signal(df: pd.DataFrame) -> dict:
    """
    볼린저밴드 — 스퀴즈 후 상/하단 브레이크아웃.

    최소 30일: 볼린저 20일 + 스퀴즈 롤링 quantile(min_periods=30)
    신규 상장/신규 분석에서 관망 편향 줄이기 위해 요구량을 타 전략 수준으로 낮춤.
    """
    if len(df) < 30:
        return {"전략": "볼린저", "시그널": "관망", "조건": "데이터 부족"}

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # 최근 스퀴즈 후 돌파인지 확인
    recent_squeeze = df["BB스퀴즈"].iloc[-10:].any()  # 최근 10일 중 스퀴즈 있었음
    vol_surge = last["거래량비율"] > 1.3 if not pd.isna(last["거래량비율"]) else False

    breakout_up = prev["종가"] <= prev["BB상단"] and last["종가"] > last["BB상단"]
    breakout_down = prev["종가"] >= prev["BB하단"] and last["종가"] < last["BB하단"]

    if recent_squeeze and breakout_up and vol_surge:
        signal = "매수"
        condition = f"스퀴즈 후 상단 돌파 + 거래량 {last['거래량비율']:.1f}배"
        stop_loss = last["BB하단"]
    elif recent_squeeze and breakout_down and vol_surge:
        signal = "매도"
        condition = f"스퀴즈 후 하단 이탈 + 거래량 {last['거래량비율']:.1f}배"
        stop_loss = last["BB상단"]
    else:
        signal = "관망"
        bb_pos = "상단 부근" if last["종가"] > last["BB중심"] else "하단 부근"
        condition = f"스퀴즈 {'있음' if recent_squeeze else '없음'}, {bb_pos}"
        stop_loss = None

    return {
        "전략": "볼린저",
        "시그널": signal,
        "조건": condition,
        "진입가": last["종가"] if signal in ["매수", "매도"] else None,
        "손절가": round(stop_loss) if stop_loss else None,
    }


# ============================================================
# 7. 그랜빌 이동평균선 8법칙
# ============================================================

def granville_signal(df: pd.DataFrame, ma_col: str = "SMA60") -> dict:
    """
    그랜빌 8법칙 — 가격과 이동평균의 관계.
    기본값은 60일선. (5/10/20/60/120/200일 모두 가능)
    """
    if len(df) < 30:
        return {"전략": f"그랜빌({ma_col})", "시그널": "관망", "조건": "데이터 부족"}

    last = df.iloc[-1]
    prev = df.iloc[-2]
    price = last["종가"]
    ma = last[ma_col]
    ma_prev = prev[ma_col]
    ma_20ago = df.iloc[-21][ma_col] if len(df) >= 21 else ma

    if pd.isna(ma):
        return {"전략": f"그랜빌({ma_col})", "시그널": "관망", "조건": "MA 데이터 부족"}

    ma_rising = ma > ma_prev
    ma_turning_up = ma_prev < ma_20ago and ma_rising
    price_crossed_up = prev["종가"] <= ma_prev and price > ma
    price_above_ma = price > ma

    # 매수 신호
    if ma_turning_up and price_crossed_up:
        signal = "매수"
        condition = f"매수1 (MA 상승전환 + 가격 돌파) @ {ma_col}"
    elif ma_rising and not price_above_ma and prev["종가"] > ma_prev:
        signal = "매수"
        condition = f"매수2 (MA 위에서 일시 이탈 후 복귀) @ {ma_col}"
    elif ma_rising and price_above_ma and (price - ma) / ma < 0.02:
        signal = "매수"
        condition = f"매수3 (MA 눌림목) @ {ma_col}"
    elif not ma_rising and (ma - price) / ma > 0.15:
        signal = "매수"
        condition = f"매수4 (MA 아래 과이격 {(ma-price)/ma*100:.1f}%) @ {ma_col}"
    # 매도 신호 — MA 기간별 차등 threshold + ADX 추세 강도 필터
    elif ma_rising and price_above_ma:
        divergence = (price - ma) / ma
        base_threshold = {"SMA20": 0.20, "SMA60": 0.30, "SMA120": 0.50}.get(ma_col, 0.20)
        adx_val = last.get("ADX14", 0) if not pd.isna(last.get("ADX14", None)) else 0
        if adx_val > 25:
            base_threshold += 0.10
        if divergence > base_threshold:
            signal = "매도"
            adx_note = f", ADX {adx_val:.0f}" if adx_val > 0 else ""
            condition = f"매도8 (MA 위 과이격 {divergence*100:.1f}% > 기준 {base_threshold*100:.0f}%{adx_note}) @ {ma_col}"
        else:
            signal = "관망"
            condition = f"MA 상승, 가격 위 (이격 {divergence*100:.1f}%, 기준 {base_threshold*100:.0f}% 미만)"
    elif not ma_rising and price_above_ma and prev["종가"] <= ma_prev:
        signal = "매도"
        condition = f"매도5 (MA 하락전환 + 가격 이탈) @ {ma_col}"
    else:
        signal = "관망"
        condition = f"MA {'상승' if ma_rising else '하락'}, 가격 {'위' if price_above_ma else '아래'}"

    stop_loss = ma * 0.98 if signal == "매수" else (ma * 1.02 if signal == "매도" else None)

    return {
        "전략": f"그랜빌({ma_col})",
        "시그널": signal,
        "조건": condition,
        "진입가": price if signal in ["매수", "매도"] else None,
        "손절가": round(stop_loss) if stop_loss else None,
    }


# ============================================================
# 8. RSI 과매수 매도 (역추세)
# ============================================================

def rsi_overbought_signal(df: pd.DataFrame, threshold: float = 80) -> dict:
    """
    RSI>80 + 52주 고가 근접 시 "매도" (과열 경고).
    기존 추세 추종 전략 대비 균형 확보용.
    """
    last = df.iloc[-1]
    rsi = last.get("RSI14")
    if rsi is None or pd.isna(rsi):
        return {"전략": "RSI과열", "시그널": "관망", "조건": "데이터 부족"}

    proximity = last.get("고가대비%", 0)  # 종가/52주고가*100

    if rsi >= threshold and proximity >= 95:
        signal = "매도"
        condition = f"RSI {rsi:.0f} 극과열 + 52주 고가 {proximity:.0f}% 근접 — 추격 금지, 부분 익절"
        stop_loss = last["종가"] * 1.03
    elif rsi >= 75:
        signal = "관망"
        condition = f"RSI {rsi:.0f} 과매수 — 신규 진입 주의"
        stop_loss = None
    else:
        signal = "관망"
        condition = f"RSI {rsi:.0f} 정상권"
        stop_loss = None

    return {
        "전략": "RSI과열",
        "시그널": signal,
        "조건": condition,
        "진입가": last["종가"] if signal == "매도" else None,
        "손절가": round(stop_loss) if stop_loss else None,
    }


# ============================================================
# 9. 평균 회귀 매도 (고이격 + 거래량 감소)
# ============================================================

def mean_reversion_signal(df: pd.DataFrame) -> dict:
    """
    20MA 대비 이격 +15% 이상 + 거래량 감소 시 "매도".
    상승이 매수세 약화와 결합되면 반전 임박.
    """
    if len(df) < 40:
        return {"전략": "평균회귀", "시그널": "관망", "조건": "데이터 부족"}

    last = df.iloc[-1]
    sma20 = last.get("SMA20")
    if sma20 is None or pd.isna(sma20):
        return {"전략": "평균회귀", "시그널": "관망", "조건": "MA 부족"}

    divergence = (last["종가"] - sma20) / sma20
    vol_ratio = last.get("거래량비율", 1.0)

    if divergence >= 0.15 and vol_ratio < 0.8:
        signal = "매도"
        condition = f"20MA 이격 {divergence*100:.1f}% + 거래량 {vol_ratio:.2f}x 감소 — 상승 탄력 약화"
        stop_loss = last["종가"] * 1.03
    elif divergence >= 0.20:
        signal = "매도"
        condition = f"20MA 이격 {divergence*100:.1f}% 극대 — 반전 리스크"
        stop_loss = last["종가"] * 1.03
    else:
        signal = "관망"
        condition = f"20MA 이격 {divergence*100:.1f}%, 거래량 {vol_ratio:.2f}x"
        stop_loss = None

    return {
        "전략": "평균회귀",
        "시그널": signal,
        "조건": condition,
        "진입가": last["종가"] if signal == "매도" else None,
        "손절가": round(stop_loss) if stop_loss else None,
    }


# ============================================================
# 10. 추세 반전 매도 (전환선 역전 + MACD 음전환)
# ============================================================

def trend_reversal_signal(df: pd.DataFrame) -> dict:
    """
    전환선-기준선 역전 + MACD 히스토 음전환 시 "매도".
    추세 종료 확정 시그널.
    """
    if len(df) < 30:
        return {"전략": "추세반전", "시그널": "관망", "조건": "데이터 부족"}

    last = df.iloc[-1]
    prev = df.iloc[-2]

    tenkan = last.get("전환선")
    kijun = last.get("기준선")
    macd_hist = last.get("MACD히스토", 0)
    macd_hist_prev = prev.get("MACD히스토", 0)

    if any(v is None or pd.isna(v) for v in [tenkan, kijun]):
        return {"전략": "추세반전", "시그널": "관망", "조건": "일목 지표 부족"}

    tenkan_below = tenkan < kijun
    tenkan_below_prev = prev["전환선"] < prev["기준선"] if not pd.isna(prev.get("전환선", float('nan'))) else False
    macd_turned_negative = macd_hist < 0 and macd_hist_prev >= 0

    # 방금 역전 발생
    just_reversed = tenkan_below and not tenkan_below_prev

    if just_reversed and macd_turned_negative:
        signal = "매도"
        condition = "전환선↓기준선 역전 + MACD 음전환 — 추세 종료 확정"
        stop_loss = kijun * 1.02
    elif just_reversed:
        signal = "매도"
        condition = "전환선↓기준선 역전 — 추세 약화 경고"
        stop_loss = kijun * 1.02
    elif tenkan_below and macd_hist < macd_hist_prev:
        signal = "관망"
        condition = "기존 역전 + MACD 약화 지속 — 보유 방어 모드"
        stop_loss = None
    else:
        signal = "관망"
        condition = f"전환선 {'위' if not tenkan_below else '아래'}, MACD 히스토 {macd_hist:.0f}"
        stop_loss = None

    return {
        "전략": "추세반전",
        "시그널": signal,
        "조건": condition,
        "진입가": last["종가"] if signal == "매도" else None,
        "손절가": round(stop_loss) if stop_loss else None,
    }


# ============================================================
# 통합 — 모든 전략 시그널
# ============================================================

def analyze_all(df: pd.DataFrame) -> list[dict]:
    """
    compute_all()된 DataFrame을 받아 모든 전략 시그널 반환.

    12개 전략: 추세 추종 9 + 역추세/매도 3 (균형).

    Returns:
        전략별 시그널 dict 리스트
    """
    return [
        # 추세 추종
        ichimoku_signal(df),
        larry_williams_signal(df),
        minervini_signal(df),
        livermore_signal(df),
        triple_screen_signal(df),
        bollinger_signal(df),
        granville_signal(df, "SMA20"),
        granville_signal(df, "SMA60"),
        granville_signal(df, "SMA120"),
        # 역추세/매도 (과열 방어)
        rsi_overbought_signal(df),
        mean_reversion_signal(df),
        trend_reversal_signal(df),
    ]


def summarize(signals: list[dict], weights: dict[str, float] | None = None,
              stock_code: str | None = None, stock_name: str | None = None) -> dict:
    """시그널 요약 — 가중 합산 + 카운트.

    가중치 우선순위:
      1. 명시 weights 인자
      2. stock_code/stock_name 주어지면 → backtest 캐시에서 자동 로드
      3. 글로벌 기본값 (STRATEGY_WEIGHTS)
    """
    w = weights
    if w is None and stock_name:
        try:
            from .backtest import load_cache
            cached = load_cache(stock_name)
            if cached:
                w = weights_from_backtest(cached)
        except Exception:
            pass
    if w is None:
        w = STRATEGY_WEIGHTS
    buy = sum(1 for s in signals if s["시그널"] == "매수")
    sell = sum(1 for s in signals if s["시그널"] == "매도")
    wait = sum(1 for s in signals if s["시그널"] == "관망")

    buy_w = sum(w.get(s["전략"], 1.0) for s in signals if s["시그널"] == "매수")
    sell_w = sum(w.get(s["전략"], 1.0) for s in signals if s["시그널"] == "매도")
    diff = buy_w - sell_w

    if diff >= 3.0:
        overall = "강한매수"
    elif diff >= 1.5:
        overall = "매수우세"
    elif diff > -1.5:
        overall = "중립"
    elif diff > -3.0:
        overall = "매도우세"
    else:
        overall = "강한매도"

    return {
        "종합": overall,
        "매수": buy,
        "매도": sell,
        "관망": wait,
        "총": len(signals),
        "매수_가중합": round(buy_w, 1),
        "매도_가중합": round(sell_w, 1),
    }


if __name__ == "__main__":
    from pykrx import stock
    from datetime import datetime, timedelta
    from indicators import compute_all

    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=500)).strftime("%Y%m%d")
    df = stock.get_market_ohlcv(start, end, "005930")
    df = df.reset_index()
    df.columns = ["날짜", "시가", "고가", "저가", "종가", "거래량", "등락률"]

    df = compute_all(df)
    signals = analyze_all(df)

    print(f"=== 삼성전자 ({df.iloc[-1]['날짜'].strftime('%Y-%m-%d')}) ===\n")
    for sig in signals:
        print(f"[{sig['시그널']}] {sig['전략']}: {sig['조건']}")
        if sig.get("진입가"):
            print(f"    진입: {sig['진입가']:,} / 손절: {sig['손절가']:,}")
        print()

    print("=== 종합 ===")
    print(summarize(signals))
