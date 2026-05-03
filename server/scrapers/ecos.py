"""
한국은행 ECOS (경제통계시스템) 어댑터 — KR 매크로 정형 데이터.

- 무료. https://ecos.bok.or.kr/api/  즉시 발급.
- StatisticSearch API: GET .../{KEY}/json/kr/{start}/{end}/{stat_code}/{cycle}/{from}/{to}/[item1]/[item2]/[item3]/[item4]
- 주요 시계열 (default 8종 — stat_code + item_code 조합):
    * 기준금리(月) / CPI(月) / 원달러환율(日) / M2(月) / 경상수지(月) / 산업생산(月) / 실업률(月) / 외환보유고(月)

⚠️ stat_code / item_code 매핑은 ECOS "통계코드검색" 페이지 기준값.
   실 호출이 실패하면 ECOS 매뉴얼에서 코드 갱신 필요 (시간 지나면 통계표 재구성될 수 있음).
   확실한 코드는 첫 실호출 시 직접 검증하고 DEFAULT_SERIES 갱신 권장.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import httpx

from server.config import settings


_BASE = "https://ecos.bok.or.kr/api/StatisticSearch"


# stat_code: (이름, item_code1, cycle, lookback_periods)
# cycle: D / M / Q / Y
DEFAULT_SERIES: dict[str, dict[str, Any]] = {
    "722Y001": {"이름": "한국은행 기준금리", "item": "0101000", "cycle": "M", "lookback": 24},
    "901Y009": {"이름": "소비자물가지수(CPI)", "item": "0", "cycle": "M", "lookback": 24},
    "731Y004": {"이름": "원/달러 환율(매매기준율)", "item": "0000003", "cycle": "D", "lookback": 30},
    "101Y004": {"이름": "M2 광의통화(평잔)", "item": "BBHA00", "cycle": "M", "lookback": 24},
    "301Y013": {"이름": "경상수지", "item": "000000", "cycle": "M", "lookback": 24},
    "901Y033": {"이름": "산업생산지수", "item": "A00", "cycle": "M", "lookback": 24},
    "901Y027": {"이름": "실업률", "item": "I61BC", "cycle": "M", "lookback": 24},
    "732Y001": {"이름": "외환보유고", "item": "99", "cycle": "M", "lookback": 24},
}


def _api_key() -> str:
    key = settings.ecos_api_key
    if not key or key.startswith("your_"):
        raise RuntimeError(
            "ECOS_API_KEY 미설정. .env 확인 (https://ecos.bok.or.kr/api/ 무료)"
        )
    return key


def _date_range(cycle: str, lookback: int) -> tuple[str, str]:
    """cycle 별 시작/종료 (ECOS 포맷: 일=YYYYMMDD, 월=YYYYMM, 분기=YYYYQ#, 연=YYYY)."""
    today = datetime.now()
    if cycle == "D":
        end = today.strftime("%Y%m%d")
        start = (today - timedelta(days=lookback)).strftime("%Y%m%d")
    elif cycle == "M":
        end = today.strftime("%Y%m")
        # lookback 개월 전
        m = today.month - lookback
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        start = f"{y:04d}{m:02d}"
    elif cycle == "Q":
        cur_q = (today.month - 1) // 3 + 1
        end = f"{today.year}Q{cur_q}"
        # lookback 분기 전
        q = cur_q - lookback
        y = today.year
        while q <= 0:
            q += 4
            y -= 1
        start = f"{y}Q{q}"
    elif cycle == "Y":
        end = str(today.year)
        start = str(today.year - lookback)
    else:
        raise ValueError(f"unknown cycle: {cycle}")
    return start, end


def fetch_kr_macro_indicators(stat_codes: list[str] | None = None) -> dict:
    """
    ECOS 주요 KR 매크로 시계열 한 번에 조회.

    stat_codes 미지정 시 DEFAULT_SERIES 8종 (기준금리/CPI/환율/M2/경상수지/산업생산/실업률/외환보유고).
    각 시계열에 대해 lookback 기간 + 최신값 + YoY(가능 시) 산출.

    반환: {stat_code: {지표명, 최신값, 단위, 날짜, YoY변화, 출처: "ECOS"}}
          호출 실패 시 {stat_code: {"error": ...}}
    """
    key = _api_key()
    if stat_codes is None:
        stat_codes = list(DEFAULT_SERIES.keys())

    result: dict = {}
    with httpx.Client(timeout=10.0) as client:
        for code in stat_codes:
            spec = DEFAULT_SERIES.get(code)
            if not spec:
                result[code] = {"error": f"unknown stat_code (DEFAULT_SERIES 미정의)"}
                continue
            cycle = spec["cycle"]
            start, end = _date_range(cycle, spec["lookback"])
            url = f"{_BASE}/{key}/json/kr/1/100/{code}/{cycle}/{start}/{end}/{spec['item']}"
            try:
                r = client.get(url)
                r.raise_for_status()
                payload = r.json()
            except Exception as e:
                result[code] = {"error": f"{type(e).__name__}: {e}"[:200]}
                continue
            # ECOS 응답: {"StatisticSearch": {"list_total_count": N, "row": [...]}}
            search = payload.get("StatisticSearch") or {}
            rows = search.get("row") or []
            if not rows:
                err = payload.get("RESULT") or payload  # 에러 페이로드 보존
                result[code] = {"이름": spec["이름"], "error": str(err)[:200]}
                continue
            # 최신값 + YoY
            try:
                rows_sorted = sorted(rows, key=lambda x: x.get("TIME") or "")
                latest = rows_sorted[-1]
                latest_val = float(latest.get("DATA_VALUE") or 0)
                latest_dt = latest.get("TIME")
                unit = latest.get("UNIT_NAME")
                # YoY: cycle 기반으로 1년 전 row 찾기
                yoy = None
                if cycle == "M":
                    target = _shift_month(latest_dt, -12)
                elif cycle == "D":
                    target = _shift_day(latest_dt, -365)
                elif cycle == "Q":
                    target = _shift_q(latest_dt, -4)
                elif cycle == "Y":
                    target = _shift_year(latest_dt, -1)
                else:
                    target = None
                if target:
                    prior = next((r for r in rows_sorted if r.get("TIME") == target), None)
                    if prior:
                        try:
                            prev_val = float(prior.get("DATA_VALUE") or 0)
                            if prev_val:
                                yoy = round((latest_val - prev_val) / abs(prev_val) * 100, 2)
                        except Exception:
                            pass
                result[code] = {
                    "이름": spec["이름"],
                    "최신값": latest_val,
                    "단위": unit,
                    "날짜": latest_dt,
                    "YoY변화": yoy,
                    "cycle": cycle,
                    "출처": "ECOS",
                }
            except Exception as e:
                result[code] = {"이름": spec["이름"], "error": f"파싱 실패: {e}"[:200]}

    return result


def _shift_month(yyyymm: str, delta: int) -> str | None:
    if not yyyymm or len(yyyymm) < 6:
        return None
    y, m = int(yyyymm[:4]), int(yyyymm[4:6])
    m += delta
    while m <= 0:
        m += 12
        y -= 1
    while m > 12:
        m -= 12
        y += 1
    return f"{y:04d}{m:02d}"


def _shift_day(yyyymmdd: str, delta_days: int) -> str | None:
    if not yyyymmdd or len(yyyymmdd) < 8:
        return None
    try:
        d = datetime.strptime(yyyymmdd, "%Y%m%d") + timedelta(days=delta_days)
        return d.strftime("%Y%m%d")
    except ValueError:
        return None


def _shift_q(yyyyq: str, delta: int) -> str | None:
    # 예: "2025Q3"
    if not yyyyq or "Q" not in yyyyq:
        return None
    y_str, q_str = yyyyq.split("Q")
    y, q = int(y_str), int(q_str)
    q += delta
    while q <= 0:
        q += 4
        y -= 1
    while q > 4:
        q -= 4
        y += 1
    return f"{y}Q{q}"


def _shift_year(yyyy: str, delta: int) -> str | None:
    try:
        return str(int(yyyy) + delta)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    import sys
    try:
        out = fetch_kr_macro_indicators()
        for code, payload in out.items():
            print(f"{code}: {payload}")
    except RuntimeError as e:
        print(f"smoke test skipped: {e}", file=sys.stderr)
