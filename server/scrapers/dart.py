"""
DART (전자공시시스템) 래퍼 — OpenDartReader 기반
- 재무제표 상세 (IS/BS/CF) — fetch_financials
- 재무 요약 + 주요 비율 — summarize_financials
- 최근 공시 목록 — fetch_disclosures
- 주요 주주 / 대주주 지분변동 — fetch_major_shareholders
"""

from datetime import datetime

import pandas as pd

from server.config import settings

DART_API_KEY = settings.dart_api_key

_dart = None


def _client():
    """OpenDartReader 싱글톤."""
    global _dart
    if _dart is None:
        if not DART_API_KEY:
            raise RuntimeError("DART_API_KEY가 .env에 없음")
        import OpenDartReader
        _dart = OpenDartReader(DART_API_KEY)
    return _dart


def _to_int(val) -> int | None:
    try:
        return int(str(val).replace(",", "").replace(" ", ""))
    except (ValueError, AttributeError, TypeError):
        return None


def _account_getter(df: pd.DataFrame):
    """
    계정명으로 값을 찾는 클로저 반환.
    `sj_div` (재무제표 구분)와 `account_nm` 조합으로 검색.
    IS와 CIS는 혼용 가능(일부 기업은 CIS만 공시).
    """
    def get(sj_divs: list[str] | str, candidates: list[str], amount_col: str = "thstrm_amount") -> int | None:
        """
        Args:
            sj_divs: 재무제표 구분 리스트 또는 단일 문자열 — "BS" / "IS" / "CIS" / "CF" / "SCE"
                    여러 개 지정 시 우선순위 순서로 매칭 시도
            candidates: 계정명 후보 (첫 번째 매칭)
        """
        if isinstance(sj_divs, str):
            sj_divs = [sj_divs]
        for sj_div in sj_divs:
            sub = df[df["sj_div"] == sj_div] if "sj_div" in df.columns else df
            if sub.empty:
                continue
            for name in candidates:
                match = sub[sub["account_nm"].str.contains(name, na=False, regex=False)]
                if not match.empty:
                    val = _to_int(match.iloc[0].get(amount_col))
                    if val is not None:
                        return val
        return None
    return get


def fetch_financials(code: str, years: int = 3, fs_div: str = "CFS") -> dict:
    """
    최근 N년 연간 재무제표 상세 (IS/BS/CF + 주요 비율).

    Args:
        code: 6자리 종목코드
        years: 조회 연도 수 (기본 3년)
        fs_div: "CFS" 연결재무제표 (기본) / "OFS" 별도재무제표

    Returns:
        {
            "연도별": [
                {
                    "연도": int,
                    # 손익계산서
                    "매출": int, "매출원가": int, "매출총이익": int,
                    "판관비": int, "영업이익": int, "영업외수익": int, "영업외비용": int,
                    "법인세차감전이익": int, "법인세": int, "순이익": int,
                    # 재무상태표
                    "유동자산": int, "비유동자산": int, "자산총계": int,
                    "유동부채": int, "비유동부채": int, "부채총계": int,
                    "자본금": int, "이익잉여금": int, "자본총계": int,
                    "현금성자산": int, "매출채권": int, "재고자산": int, "유형자산": int,
                    # 현금흐름표
                    "영업CF": int, "투자CF": int, "재무CF": int, "Capex": int, "FCF": int,
                    # 주요 비율
                    "영업이익률": float, "순이익률": float, "매출총이익률": float,
                    "부채비율": float, "유동비율": float, "자기자본비율": float,
                    "ROE": float, "ROA": float, "이자보상배율": float,
                    # YoY
                    "매출_YoY": float, "영업이익_YoY": float, "순이익_YoY": float,
                }, ...
            ],
            "오류": [...] (있을 경우)
        }
    """
    dart = _client()
    current_year = datetime.now().year
    target_years = list(range(current_year - years, current_year))
    result = {"연도별": []}

    for y in target_years:
        try:
            fs = dart.finstate_all(code, y, reprt_code="11011", fs_div=fs_div)
            if fs is None or fs.empty:
                # fallback: finstate (요약) 사용
                fs = dart.finstate(code, y, reprt_code="11011")
                if fs is None or fs.empty:
                    continue

            get = _account_getter(fs)

            # 손익계산서 (IS/CIS — 일부 기업은 CIS만 공시)
            IS_OR_CIS = ["IS", "CIS"]
            revenue = get(IS_OR_CIS, ["영업수익", "매출액", "수익(매출액)"])
            cogs = get(IS_OR_CIS, ["매출원가"])
            gross = get(IS_OR_CIS, ["매출총이익"]) or ((revenue - cogs) if (revenue and cogs) else None)
            sga = get(IS_OR_CIS, ["판매비와관리비", "판매비와 관리비"])
            op_expense = get(IS_OR_CIS, ["영업비용"])  # 게임사/플랫폼은 '영업비용' 단일 계정 사용
            op_income = get(IS_OR_CIS, ["영업이익(손실)", "영업이익"])
            non_op_rev = get(IS_OR_CIS, ["영업외수익", "금융수익", "기타수익"])
            non_op_exp = get(IS_OR_CIS, ["영업외비용", "금융비용", "기타비용"])
            pretax = get(IS_OR_CIS, ["법인세비용차감전순이익", "법인세비용차감전순이익(손실)", "법인세차감전"])
            tax = get(IS_OR_CIS, ["법인세비용"])
            net_income = get(IS_OR_CIS, ["연결당기순이익(손실)", "당기순이익(손실)", "당기순이익", "지배기업의 소유주에게 귀속되는 당기순이익"])
            interest_exp = get(IS_OR_CIS, ["이자비용", "금융비용"])

            # 재무상태표 (BS)
            current_assets = get(["BS"], ["유동자산"])
            non_current_assets = get(["BS"], ["비유동자산"])
            total_assets = get(["BS"], ["자산총계"])
            current_liab = get(["BS"], ["유동부채"])
            non_current_liab = get(["BS"], ["비유동부채"])
            total_liab = get(["BS"], ["부채총계"])
            capital = get(["BS"], ["자본금"])
            retained = get(["BS"], ["이익잉여금", "이익잉여금(결손금)"])
            total_equity = get(["BS"], ["자본총계"])
            cash = get(["BS"], ["현금및현금성자산", "현금성자산"])
            receivables = get(["BS"], ["매출채권", "매출채권및기타채권"])
            inventory = get(["BS"], ["재고자산", "유동재고자산"])
            ppe = get(["BS"], ["유형자산"])

            # 현금흐름표 (CF)
            ocf = get(["CF"], ["영업활동현금흐름", "영업활동으로인한현금흐름", "영업활동 현금흐름"])
            icf = get(["CF"], ["투자활동현금흐름", "투자활동으로인한현금흐름", "투자활동 현금흐름"])
            fcf_activity = get(["CF"], ["재무활동현금흐름", "재무활동으로인한현금흐름", "재무활동 현금흐름"])
            # Capex: 유형자산 취득 (음수/양수 혼재 → 절대값)
            capex = get(["CF"], ["유형자산의 취득", "유형자산의취득", "유형자산 취득"])
            capex = abs(capex) if capex is not None else None
            fcf = ocf - capex if (ocf is not None and capex is not None) else None

            year_data = {
                "연도": y,
                # IS
                "매출": revenue, "매출원가": cogs, "매출총이익": gross,
                "판관비": sga, "영업이익": op_income,
                "영업외수익": non_op_rev, "영업외비용": non_op_exp,
                "법인세차감전이익": pretax, "법인세": tax, "순이익": net_income,
                "이자비용": interest_exp,
                # BS
                "유동자산": current_assets, "비유동자산": non_current_assets, "자산총계": total_assets,
                "유동부채": current_liab, "비유동부채": non_current_liab, "부채총계": total_liab,
                "자본금": capital, "이익잉여금": retained, "자본총계": total_equity,
                "현금성자산": cash, "매출채권": receivables, "재고자산": inventory, "유형자산": ppe,
                # CF
                "영업CF": ocf, "투자CF": icf, "재무CF": fcf_activity,
                "Capex": capex, "FCF": fcf,
            }

            # 주요 비율
            def _pct(num, den):
                return round(num / den * 100, 1) if (num is not None and den and den != 0) else None

            year_data["매출총이익률"] = _pct(gross, revenue)
            year_data["영업이익률"] = _pct(op_income, revenue)
            year_data["순이익률"] = _pct(net_income, revenue)
            year_data["부채비율"] = _pct(total_liab, total_equity)
            year_data["유동비율"] = _pct(current_assets, current_liab)
            year_data["자기자본비율"] = _pct(total_equity, total_assets)
            year_data["ROE"] = _pct(net_income, total_equity)
            year_data["ROA"] = _pct(net_income, total_assets)
            if op_income is not None and interest_exp and interest_exp != 0:
                year_data["이자보상배율"] = round(op_income / interest_exp, 1)
            # 순이익/영업이익 괴리 (일회성 의심 감지용)
            if op_income and op_income != 0:
                year_data["순이익_영업이익_배율"] = round(net_income / op_income, 1) if net_income is not None else None

            result["연도별"].append(year_data)
        except Exception as e:
            result.setdefault("오류", []).append(f"{y}년: {e}")

    # YoY 성장률
    for i in range(1, len(result["연도별"])):
        curr, prev = result["연도별"][i], result["연도별"][i - 1]
        for key in ["매출", "영업이익", "순이익", "영업CF", "FCF"]:
            c, p = curr.get(key), prev.get(key)
            if c is not None and p and p != 0:
                curr[f"{key}_YoY"] = round((c - p) / abs(p) * 100, 1)

    return result


def summarize_financials(fin: dict) -> dict:
    """
    fetch_financials 결과를 종합 판단용 핵심 지표로 요약.
    """
    years = fin.get("연도별", [])
    if not years:
        return {"error": "재무 데이터 없음"}

    latest = years[-1]
    summary = {
        "최근연도": latest["연도"],
        # 규모 (억원 단위)
        "매출_억": round(latest["매출"] / 1e8) if latest.get("매출") else None,
        "영업이익_억": round(latest["영업이익"] / 1e8) if latest.get("영업이익") else None,
        "순이익_억": round(latest["순이익"] / 1e8) if latest.get("순이익") else None,
        "영업CF_억": round(latest["영업CF"] / 1e8) if latest.get("영업CF") else None,
        "FCF_억": round(latest["FCF"] / 1e8) if latest.get("FCF") else None,
        "Capex_억": round(latest["Capex"] / 1e8) if latest.get("Capex") else None,
        "현금_억": round(latest["현금성자산"] / 1e8) if latest.get("현금성자산") else None,
        # 수익성
        "매출총이익률": latest.get("매출총이익률"),
        "영업이익률": latest.get("영업이익률"),
        "순이익률": latest.get("순이익률"),
        "ROE": latest.get("ROE"),
        "ROA": latest.get("ROA"),
        # 안정성
        "부채비율": latest.get("부채비율"),
        "유동비율": latest.get("유동비율"),
        "자기자본비율": latest.get("자기자본비율"),
        "이자보상배율": latest.get("이자보상배율"),
        # 성장성
        "매출_YoY": latest.get("매출_YoY"),
        "영업이익_YoY": latest.get("영업이익_YoY"),
        "순이익_YoY": latest.get("순이익_YoY"),
        "FCF_YoY": latest.get("FCF_YoY"),
    }

    # 경고 플래그
    warnings = []
    ratio = latest.get("순이익_영업이익_배율")
    if ratio and ratio > 2:
        warnings.append(f"순이익이 영업이익의 {ratio}배 — 일회성 이익(자산매각/법인세환급/평가이익) 의심. 현금흐름표 확인 필요")
    if latest.get("영업이익률") is not None and latest["영업이익률"] < 5:
        warnings.append(f"영업이익률 {latest['영업이익률']}% — 수익성 취약")
    if latest.get("부채비율") is not None and latest["부채비율"] > 200:
        warnings.append(f"부채비율 {latest['부채비율']}% — 재무 레버리지 과도")
    if latest.get("유동비율") is not None and latest["유동비율"] < 100:
        warnings.append(f"유동비율 {latest['유동비율']}% — 단기 지급능력 위험")
    if latest.get("이자보상배율") is not None and latest["이자보상배율"] < 3:
        warnings.append(f"이자보상배율 {latest['이자보상배율']} — 이자 감당 부담")
    if latest.get("영업CF") is not None and latest.get("순이익") and latest["영업CF"] < latest["순이익"] * 0.5:
        warnings.append("영업CF가 순이익의 50% 미만 — 이익 질 낮음 (현금 전환율 저조)")

    summary["경고"] = warnings
    return summary


def fetch_disclosures(code: str, days: int = 30) -> pd.DataFrame:
    """최근 N일 공시 목록."""
    dart = _client()
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - pd.Timedelta(days=days)).strftime("%Y%m%d")
    try:
        df = dart.list(code, start=start, end=end)
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        return pd.DataFrame({"error": [str(e)]})


def fetch_major_shareholders(code: str) -> pd.DataFrame:
    """대주주 현황."""
    dart = _client()
    try:
        df = dart.major_shareholders(code)
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        return pd.DataFrame({"error": [str(e)]})


def fetch_major_shareholders_exec(code: str) -> pd.DataFrame:
    """임원/주요주주 지분변동."""
    dart = _client()
    try:
        df = dart.major_shareholders_exec(code)
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        return pd.DataFrame({"error": [str(e)]})


def fetch_next_earnings_date(code: str) -> dict:
    """
    차기 실적 발표 예정일 추정.

    방식:
      1. 최근 실적 발표 공시 패턴에서 분기 발표 주기 추정
      2. 마지막 발표일 + 약 90일 → 차기 예상일
      3. 공시 목록에서 "실적공시예정" "주요경영사항" 등 사전 공시 탐색

    Returns:
        {
            "마지막_발표일": str | None,
            "차기_예상일": str | None,
            "D_remaining": int | None,   # 오늘부터 차기까지 일수
            "earnings_window": bool,     # D-7 이내면 True
            "근거": str,
        }
    """
    from datetime import datetime, timedelta

    dart = _client()
    try:
        # 최근 60일 공시에서 실적 관련 공시 추출
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")
        df = dart.list(code, start=start, end=end)
        if df is None or df.empty:
            return {
                "마지막_발표일": None, "차기_예상일": None, "D_remaining": None,
                "earnings_window": False, "근거": "공시 데이터 없음",
            }

        # "연결재무제표기준영업(잠정)실적", "분기보고서", "사업보고서" 패턴
        earnings_reports = df[
            df["report_nm"].str.contains(
                r"영업\(잠정\)실적|분기보고서|반기보고서|사업보고서", regex=True, na=False
            )
        ] if "report_nm" in df.columns else pd.DataFrame()

        if earnings_reports.empty:
            return {
                "마지막_발표일": None, "차기_예상일": None, "D_remaining": None,
                "earnings_window": False, "근거": "최근 120일 실적공시 없음",
            }

        last_date_str = str(earnings_reports.iloc[0].get("rcept_dt", ""))[:8]
        if len(last_date_str) != 8:
            return {
                "마지막_발표일": None, "earnings_window": False,
                "근거": "공시일 파싱 실패",
            }

        last_date = datetime.strptime(last_date_str, "%Y%m%d")
        # 차기 실적: 마지막 발표 + 약 90일 (분기 주기)
        next_expected = last_date + timedelta(days=90)
        d_remaining = (next_expected - datetime.now()).days

        return {
            "마지막_발표일": last_date.strftime("%Y-%m-%d"),
            "차기_예상일": next_expected.strftime("%Y-%m-%d"),
            "D_remaining": d_remaining,
            "earnings_window": -7 <= d_remaining <= 7,
            "근거": f"마지막 실적공시 {last_date_str} + 90일 추정",
        }
    except Exception as e:
        return {
            "마지막_발표일": None, "earnings_window": False,
            "근거": f"조회 실패: {e}",
        }


if __name__ == "__main__":
    code = "036570"
    print(f"=== {code} 재무 상세 ===")
    fin = fetch_financials(code, years=3)
    for y in fin.get("연도별", []):
        print(f"\n[{y['연도']}]")
        for k, v in y.items():
            if k == "연도": continue
            if isinstance(v, int) and abs(v) > 1e6:
                print(f"  {k}: {v/1e8:,.0f}억")
            else:
                print(f"  {k}: {v}")
    print("\n=== 요약 ===")
    import json
    print(json.dumps(summarize_financials(fin), indent=2, ensure_ascii=False))
