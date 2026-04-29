"""
KRX OpenAPI 기반 시장 데이터 (공매도, 대차 등).
pykrx 크롤링 대신 KRX 공식 OpenAPI 사용.

인증: .env의 KRX_API_KEY를 HTTP Header AUTH_KEY로 전송
엔드포인트: http://data-dbg.krx.co.kr/svc/apis/srt/...
"""

from datetime import datetime, timedelta

import pandas as pd
import requests
import urllib3

from server.config import settings

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

KRX_API_KEY = settings.krx_api_key
BASE_URL = "http://data-dbg.krx.co.kr/svc/apis/srt"

HEADERS = {
    "AUTH_KEY": KRX_API_KEY or "",
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def _fetch(endpoint: str, bas_dd: str) -> list[dict]:
    """KRX OpenAPI 호출 → OutBlock_1 배열 반환."""
    if not KRX_API_KEY:
        raise RuntimeError("KRX_API_KEY가 .env에 설정되지 않음")

    url = f"{BASE_URL}/{endpoint}"
    resp = requests.get(url, headers=HEADERS, params={"basDd": bas_dd}, verify=False, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("OutBlock_1", []) or data.get("OutBlock_2", []) or []


def _dt(offset: int = 0) -> str:
    return (datetime.now() - timedelta(days=offset)).strftime("%Y%m%d")


def _prev_business_days(n: int, end_offset: int = 0) -> list[str]:
    """영업일 기준 최근 N일 (주말 제외) 날짜 목록."""
    days = []
    offset = end_offset
    while len(days) < n:
        d = datetime.now() - timedelta(days=offset)
        if d.weekday() < 5:  # 월~금
            days.append(d.strftime("%Y%m%d"))
        offset += 1
    return days


def fetch_shorting_balance(code: str, days: int = 20, market: str = "kospi") -> pd.DataFrame:
    """
    공매도 잔고 시계열 조회 (종목별).

    Args:
        code: 6자리 종목코드
        days: 조회할 영업일 수
        market: 'kospi' 또는 'kosdaq'

    Returns:
        DataFrame[날짜, 종목코드, 종목명, 공매도잔고수량, 공매도잔고금액, 잔고비중, ...]
    """
    endpoint = "sbd_isu_stat" if market == "kospi" else "ksq_sbd_isu_stat"
    rows = []

    for bas_dd in _prev_business_days(days, end_offset=1):
        try:
            items = _fetch(endpoint, bas_dd)
            for item in items:
                if item.get("ISU_CD") == code or item.get("ISU_SRT_CD") == code:
                    item["조회일"] = bas_dd
                    rows.append(item)
                    break
        except Exception:
            continue

    return pd.DataFrame(rows)


def fetch_shorting_trade(code: str, days: int = 20, market: str = "kospi") -> pd.DataFrame:
    """
    공매도 거래 시계열 조회.

    Returns:
        DataFrame[거래량, 거래대금, 공매도거래량, 공매도거래대금, 공매도비중 등]
    """
    endpoint = "sbd_bydd_trd" if market == "kospi" else "ksq_sbd_bydd_trd"
    rows = []

    for bas_dd in _prev_business_days(days, end_offset=1):
        try:
            items = _fetch(endpoint, bas_dd)
            for item in items:
                if item.get("ISU_CD") == code or item.get("ISU_SRT_CD") == code:
                    item["조회일"] = bas_dd
                    rows.append(item)
                    break
        except Exception:
            continue

    return pd.DataFrame(rows)


def analyze_shorting(code: str, days: int = 20, market: str = "kospi") -> dict:
    """
    공매도 종합 분석.
    - 잔고 비중 추이 (증감률)
    - 공매도 거래 비중
    - 해석 (급증/급감/횡보)
    """
    balance = fetch_shorting_balance(code, days, market)
    trade = fetch_shorting_trade(code, days, market)

    if balance.empty and trade.empty:
        return {"error": "데이터 조회 실패 — API 키 승인 여부 확인 (KRX 포털에서 서비스별 이용신청 필요)"}

    result = {"종목코드": code}

    # 잔고 분석
    if not balance.empty:
        # 컬럼명은 응답에 따라 유연하게 감지
        ratio_col = next((c for c in balance.columns if "BAL" in c and "RTO" in c), None)
        qty_col = next((c for c in balance.columns if "BAL_QTY" in c), None)

        if ratio_col:
            try:
                balance["_ratio"] = pd.to_numeric(balance[ratio_col], errors="coerce")
                balance = balance.sort_values("조회일")
                current = float(balance["_ratio"].iloc[-1])
                start = float(balance["_ratio"].iloc[0])
                change = (current - start) / start * 100 if start > 0 else 0

                if change > 30:
                    trend = "급증"
                    interp = "공매도 세력 확대 → 하락 베팅 증가. 단 숏 스퀴즈 가능성"
                elif change > 10:
                    trend = "증가"
                    interp = "공매도 잔고 증가 추세"
                elif change > -10:
                    trend = "횡보"
                    interp = "공매도 잔고 안정적"
                elif change > -30:
                    trend = "감소"
                    interp = "공매도 숏 커버링 진행 (매수 압력)"
                else:
                    trend = "급감"
                    interp = "대규모 숏 커버링 → 급반등 가능성 ↑"

                result["공매도_잔고비중_현재"] = round(current, 2)
                result["공매도_잔고비중_변화율"] = round(change, 1)
                result["잔고_추세"] = trend
                result["해석"] = interp
            except Exception as e:
                result["잔고_오류"] = str(e)

    # 거래 분석
    if not trade.empty:
        vol_ratio_col = next((c for c in trade.columns if "CVSRTSELL" in c and "RTO" in c), None)
        if vol_ratio_col:
            try:
                trade["_vr"] = pd.to_numeric(trade[vol_ratio_col], errors="coerce")
                recent_avg = float(trade["_vr"].tail(5).mean())
                result[f"최근5일_공매도거래비중_평균"] = round(recent_avg, 2)
            except Exception:
                pass

    return result


# ============================================================
# 주식 시세 / 시가총액 (KRX OpenAPI /sto/ 엔드포인트)
# ============================================================

STK_BASE_URL = "http://data-dbg.krx.co.kr/svc/apis/sto"


def _fetch_stk(endpoint: str, params: dict) -> list[dict]:
    """KRX OpenAPI 주식 엔드포인트 호출."""
    if not KRX_API_KEY:
        raise RuntimeError("KRX_API_KEY가 .env에 설정되지 않음")
    url = f"{STK_BASE_URL}/{endpoint}"
    resp = requests.get(url, headers=HEADERS, params={"AUTH_KEY": KRX_API_KEY, **params}, verify=False, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("OutBlock_1", [])


def fetch_market_cap(code: str, date: str | None = None) -> dict:
    """
    KRX OpenAPI로 종목의 시가총액/거래대금/상장주식수 조회.
    KOSPI/KOSDAQ 자동 탐색 (stk_bydd_trd → ksq_bydd_trd 순).

    Args:
        code: 6자리 종목코드 (예: '005930')
        date: 'YYYYMMDD' 형식. None이면 최근 영업일 자동 탐색.

    Returns:
        {"시가총액": int, "거래대금": int, "상장주식수": int, "종가": int, "시장": str} 또는 빈 dict.
    """
    if date is None:
        dates = _prev_business_days(3, end_offset=0)
    else:
        dates = [date]

    for d in dates:
        for endpoint, mkt in [("stk_bydd_trd", "KOSPI"), ("ksq_bydd_trd", "KOSDAQ")]:
            try:
                items = _fetch_stk(endpoint, {"basDd": d})
                for item in items:
                    isu_cd = item.get("ISU_CD", "") or item.get("ISU_SRT_CD", "")
                    if isu_cd == code or isu_cd.endswith(code):
                        return {
                            "시가총액": int(item.get("MKTCAP", 0)),
                            "거래대금": int(item.get("ACC_TRDVAL", 0)),
                            "상장주식수": int(item.get("LIST_SHRS", 0)),
                            "종가": int(item.get("TDD_CLSPRC", 0)),
                            "시장": mkt,
                            "기준일": d,
                        }
            except Exception:
                continue
    return {}


def fetch_all_stocks(date: str | None = None, markets: list[str] | None = None) -> list[dict]:
    """
    KOSPI + KOSDAQ 전체 시세 일괄 조회 (유니버스 구성용).

    Args:
        date: 'YYYYMMDD'. None이면 최근 영업일 자동.
        markets: ["KOSPI", "KOSDAQ"] 기본. 일부만 원하면 지정.

    Returns:
        [{"종목코드": str, "종목명": str, "시장": str, "시가총액": int, "거래대금": int,
          "종가": int, "거래량": int, "등락률": float, ...}, ...]
    """
    markets = markets or ["KOSPI", "KOSDAQ"]
    endpoint_map = {"KOSPI": "stk_bydd_trd", "KOSDAQ": "ksq_bydd_trd"}

    if date is None:
        dates = _prev_business_days(5, end_offset=0)
    else:
        dates = [date]

    all_rows = []
    for d in dates:
        combined = []
        for mkt in markets:
            ep = endpoint_map.get(mkt)
            if not ep:
                continue
            try:
                items = _fetch_stk(ep, {"basDd": d})
                for item in items:
                    if not item.get("ISU_CD"):
                        continue
                    combined.append({
                        "종목코드": item["ISU_CD"],
                        "종목명": item.get("ISU_NM", ""),
                        "시장": mkt,
                        "시가총액": int(item.get("MKTCAP", 0) or 0),
                        "거래대금": int(item.get("ACC_TRDVAL", 0) or 0),
                        "거래량": int(item.get("ACC_TRDVOL", 0) or 0),
                        "상장주식수": int(item.get("LIST_SHRS", 0) or 0),
                        "종가": int(item.get("TDD_CLSPRC", 0) or 0),
                        "등락률": float(item.get("FLUC_RT", 0) or 0),
                        "기준일": d,
                    })
            except Exception:
                continue
        if combined:
            return combined  # 첫 성공한 날짜 반환

    return []


if __name__ == "__main__":
    print("=== 삼성전자 공매도 (KOSPI) ===")
    print(analyze_shorting("005930", days=20, market="kospi"))
    print()
    print("=== 삼성전자 시가총액 (KRX) ===")
    print(fetch_market_cap("005930"))
