"""
네이버 금융 크롤러
- 분봉 데이터 (체결시각별)
- 일별 시세 (시가/고가/저가/종가/거래량)
- 기관/외국인 수급
"""

import requests
import urllib3
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://finance.naver.com/item"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def _parse_number(text: str) -> int | float | None:
    """숫자 문자열에서 콤마/공백 제거 후 숫자 변환."""
    if not text:
        return None
    cleaned = text.strip().replace(",", "").replace("+", "")
    if not cleaned or cleaned == "\xa0":
        return None
    try:
        return int(cleaned)
    except ValueError:
        try:
            return float(cleaned)
        except ValueError:
            return None


def _fetch_page(url: str, params: dict) -> BeautifulSoup:
    """네이버 금융 페이지를 가져와서 BeautifulSoup 객체로 반환."""
    resp = requests.get(url, params=params, headers=HEADERS, verify=False)
    resp.encoding = "euc-kr"
    return BeautifulSoup(resp.text, "lxml")


def _parse_table_rows(soup: BeautifulSoup, table_index: int = 0) -> list[list[str]]:
    """table.type2에서 데이터 행만 추출."""
    tables = soup.select("table.type2")
    if not tables or table_index >= len(tables):
        return []

    rows = []
    for tr in tables[table_index].select("tr[onmouseover]"):
        tds = tr.select("td")
        row = [td.get_text(strip=True) for td in tds]
        if row and row[0] and row[0] != "\xa0":
            rows.append(row)
    return rows


def _get_sign(td) -> str:
    """전일비 셀에서 상승/하락 부호 판별."""
    blind = td.select_one("span.blind")
    if blind:
        text = blind.get_text(strip=True)
        if "상승" in text:
            return "+"
        if "하락" in text:
            return "-"
    return ""


def fetch_intraday(code: str, pages: int = 1) -> pd.DataFrame:
    """
    분봉(체결시각별) 데이터 조회.

    Args:
        code: 6자리 종목코드 (예: '005930')
        pages: 가져올 페이지 수 (1페이지 = 약 40행)

    Returns:
        DataFrame[체결시각, 체결가, 전일비, 매도, 매수, 거래량, 변동량]
    """
    all_rows = []

    for page in range(1, pages + 1):
        soup = _fetch_page(f"{BASE_URL}/sise_time.naver", {"code": code, "page": page})
        rows = _parse_table_rows(soup)

        for row in rows:
            if len(row) >= 7:
                all_rows.append({
                    "체결시각": row[0],
                    "체결가": _parse_number(row[1]),
                    "전일비": _parse_number(row[2]),
                    "매도": _parse_number(row[3]),
                    "매수": _parse_number(row[4]),
                    "거래량": _parse_number(row[5]),
                    "변동량": _parse_number(row[6]),
                })

    return pd.DataFrame(all_rows)


def fetch_daily(code: str, pages: int = 5) -> pd.DataFrame:
    """
    일별 시세 데이터 조회.

    Args:
        code: 6자리 종목코드
        pages: 가져올 페이지 수 (1페이지 = 약 10행)

    Returns:
        DataFrame[날짜, 종가, 전일비, 시가, 고가, 저가, 거래량]
    """
    all_rows = []

    for page in range(1, pages + 1):
        soup = _fetch_page(f"{BASE_URL}/sise_day.naver", {"code": code, "page": page})
        table = soup.select("table.type2")
        if not table:
            break

        for tr in table[0].select("tr[onmouseover]"):
            tds = tr.select("td")
            if len(tds) < 7:
                continue

            date_text = tds[0].get_text(strip=True)
            if not date_text or date_text == "\xa0":
                continue

            sign = _get_sign(tds[2])
            diff_val = _parse_number(tds[2].get_text(strip=True).replace("상승", "").replace("하락", ""))

            all_rows.append({
                "날짜": date_text,
                "종가": _parse_number(tds[1].get_text(strip=True)),
                "전일비": f"{sign}{diff_val}" if diff_val else 0,
                "시가": _parse_number(tds[3].get_text(strip=True)),
                "고가": _parse_number(tds[4].get_text(strip=True)),
                "저가": _parse_number(tds[5].get_text(strip=True)),
                "거래량": _parse_number(tds[6].get_text(strip=True)),
            })

    df = pd.DataFrame(all_rows)
    if not df.empty:
        df["날짜"] = pd.to_datetime(df["날짜"], format="%Y.%m.%d")
        df = df.sort_values("날짜", ascending=False).reset_index(drop=True)
    return df


def fetch_investor(code: str, pages: int = 5) -> pd.DataFrame:
    """
    기관/외국인 수급 데이터 조회.

    Args:
        code: 6자리 종목코드
        pages: 가져올 페이지 수 (1페이지 = 약 20행)

    Returns:
        DataFrame[날짜, 종가, 등락률, 거래량, 기관순매매, 외국인순매매, 외국인보유주수, 외국인보유율]
    """
    all_rows = []

    for page in range(1, pages + 1):
        soup = _fetch_page(f"{BASE_URL}/frgn.naver", {"code": code, "page": page})
        rows = _parse_table_rows(soup, table_index=1)

        for row in rows:
            if len(row) >= 9:
                all_rows.append({
                    "날짜": row[0],
                    "종가": _parse_number(row[1]),
                    "등락률": row[3],
                    "거래량": _parse_number(row[4]),
                    "기관순매매": _parse_number(row[5]),
                    "외국인순매매": _parse_number(row[6]),
                    "외국인보유주수": _parse_number(row[7]),
                    "외국인보유율": row[8],
                })

    df = pd.DataFrame(all_rows)
    if not df.empty:
        df["날짜"] = pd.to_datetime(df["날짜"], format="%Y.%m.%d")
        df = df.sort_values("날짜", ascending=False).reset_index(drop=True)
    return df


def fetch_realtime_price(code: str) -> dict:
    """
    네이버 금융 메인 페이지에서 실시간 현재가 조회.
    **장 마감 후에도 시간외 단일가가 자동 반영**됨 (네이버가 실시간 갱신).

    Returns:
        {
          code, price, change, change_pct,
          prev_close, open, high, low, volume,
          is_afterhours (bool, KST 15:31~18:10 사이 True),
          base_time (ISO),
          source: 'naver_realtime'
        }
    """
    import re
    from datetime import datetime
    from zoneinfo import ZoneInfo

    url = f"https://finance.naver.com/item/main.naver?code={code}"
    resp = requests.get(url, headers=HEADERS, verify=False, timeout=10)
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "lxml")

    # 네이버는 두 개 섹션 제공:
    #   #rate_info_krx  — 한국거래소 (KRX, 정규장)
    #   #rate_info_nxt  — 넥스트레이드 (NXT, 대체거래소, 연장 세션 + 실시간 반영)
    # NXT 가 있으면 더 최신 가격 → 우선 사용
    nxt_section = soup.select_one("#rate_info_nxt")
    krx_section = soup.select_one("#rate_info_krx")
    section = nxt_section or krx_section or soup
    exchange = "NXT" if nxt_section else ("KRX" if krx_section else "unknown")

    # 현재가
    price_el = section.select_one("p.no_today span.blind")
    price = _parse_number(price_el.text) if price_el else None

    # 전일 대비
    exday_el = section.select_one("p.no_exday")
    change = None
    change_pct = None
    if exday_el:
        spans = exday_el.select("span.blind")
        texts = [s.text.strip() for s in spans]
        for t in texts:
            if "%" in t:
                change_pct = _parse_number(t.replace("%", ""))
            elif t and change is None:
                change = _parse_number(t)
        down_icon = exday_el.select_one("em.no_down, span.no_down")
        if down_icon:
            if change is not None:
                change = -abs(change)
            if change_pct is not None:
                change_pct = -abs(change_pct)

    # 상세 시세 테이블 (#middle table.no_info 또는 table.rate_info)
    # 전일·시가·고가·저가·거래량
    def _get_info_value(label: str) -> int | float | None:
        """테이블에서 label 에 해당하는 값 텍스트 찾기."""
        for th in soup.select("table th"):
            if th.get_text(strip=True) == label:
                td = th.find_next("td") or th.find_parent("tr").find("td") if th.find_parent("tr") else None
                if td:
                    span = td.select_one("span.blind") or td
                    return _parse_number(span.get_text(strip=True))
        return None

    prev_close = _get_info_value("전일")
    open_p = _get_info_value("시가")
    high = _get_info_value("고가")
    low = _get_info_value("저가")
    volume = _get_info_value("거래량")

    # 장 상태 판정 — 장 마감 후 15:31~18:10 KST 라면 시간외 가능성
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    is_weekday = now.weekday() < 5
    t = now.time()
    from datetime import time as dtime
    is_afterhours = is_weekday and (dtime(15, 31) <= t <= dtime(18, 10))

    return {
        "code": code,
        "price": price,
        "change": change,
        "change_pct": change_pct,
        "prev_close": prev_close,
        "open": open_p,
        "high": high,
        "low": low,
        "volume": volume,
        "exchange": exchange,
        "is_afterhours": is_afterhours,
        "base_time": now.isoformat(),
        "source": "naver_realtime",
    }


def fetch_fundamentals(code: str) -> dict:
    """
    종목 펀더멘털 조회. KRX OpenAPI 시가총액을 우선, 네이버 금융을 fallback으로 사용.

    Args:
        code: 6자리 종목코드

    Returns:
        {
            "시가총액": int (억원 단위),
            "시가총액_원": int (원 단위, KRX API 성공 시),
            "PER": float, "PBR": float,
            "EPS": int (원), "BPS": int (원),
            "배당수익률": float (%),
            "업종": str,
            "외국인소진율": float (%),
            "52주최고": int, "52주최저": int,
            "상장주식수": int (KRX API 성공 시),
        }
    """
    # KRX OpenAPI로 시가총액 우선 조회
    krx_data = {}
    try:
        from server.scrapers.krx import fetch_market_cap
        krx_data = fetch_market_cap(code)
    except Exception:
        pass

    import re
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    resp = requests.get(url, headers=HEADERS, verify=False, timeout=10)
    # 메인 페이지는 UTF-8 (다른 네이버 페이지들과 다름)
    resp.encoding = "utf-8"
    html = resp.text
    soup = BeautifulSoup(html, "lxml")

    result = {}

    def _text(selector: str) -> str | None:
        el = soup.select_one(selector)
        return el.get_text(strip=True) if el else None

    def _num(text: str | None, as_int: bool = False) -> int | float | None:
        if not text or text in ("N/A", "", "-"):
            return None
        cleaned = text.replace(",", "").replace("%", "").strip()
        try:
            return int(cleaned) if as_int else float(cleaned)
        except (ValueError, TypeError):
            return None

    # PER, PBR, EPS, 배당수익률 — ID 기반
    result["PER"] = _num(_text("#_per"))
    result["PBR"] = _num(_text("#_pbr"))
    result["EPS"] = _num(_text("#_eps"), as_int=True)
    result["배당수익률"] = _num(_text("#_dvr"))

    # 시가총액(억원): "시가총액(억)" 라벨 뒤 첫 <td> 에 노출됨 (정적 렌더)
    result["시가총액"] = None
    m = re.search(r'시가총액\(억\).*?<td>([\d,]+)</td>', html, re.DOTALL)
    if m:
        try:
            result["시가총액"] = int(m.group(1).replace(",", ""))  # 억원 단위
        except ValueError:
            pass

    # BPS: #_pbr 부모 td에서 두 번째 em
    pbr_el = soup.select_one("#_pbr")
    if pbr_el:
        td = pbr_el.find_parent("td")
        if td:
            ems = td.find_all("em")
            if len(ems) >= 2:
                result["BPS"] = _num(ems[1].get_text(strip=True), as_int=True)

    # 52주 최고/최저
    for tr in soup.select(".aside_invest_info table.rwidth tbody tr"):
        th = tr.find("th")
        if th and "52주" in th.get_text():
            ems = tr.find_all("em")
            if len(ems) >= 2:
                result["52주최고"] = _num(ems[0].get_text(strip=True), as_int=True)
                result["52주최저"] = _num(ems[1].get_text(strip=True), as_int=True)
            break

    # 외국인소진율
    for tr in soup.select(".aside_invest_info table.lwidth tbody tr"):
        th = tr.find("th")
        if th and "외국인" in th.get_text():
            em = tr.find("em")
            if em:
                result["외국인소진율"] = _num(em.get_text(strip=True))
            break

    # 업종
    sector_el = soup.select_one(".trade_compare h4 em a")
    if sector_el:
        result["업종"] = sector_el.get_text(strip=True)

    # KRX API 시가총액이 있으면 우선 사용 (원 단위 → 억원 변환)
    if krx_data.get("시가총액"):
        result["시가총액_원"] = krx_data["시가총액"]
        result["시가총액"] = krx_data["시가총액"] // 100_000_000
        result["상장주식수"] = krx_data.get("상장주식수", 0)
        result["거래대금"] = krx_data.get("거래대금", 0)

    return result


def fetch_research_reports(code: str, max_pages: int = 2, days: int = 90) -> list[dict]:
    """
    네이버 증권 리서치 종목 리포트 수집 (KR 컨센서스 fallback).

    각 리포트 메타 (broker / 발행일 / 제목 / URL) + 상세 페이지에서 목표가 / 투자의견 추출.

    Args:
        code: 6자리 종목코드
        max_pages: 목록 페이지 수 (1 페이지당 약 20개)
        days: 발행일 cutoff (오늘 - days 이전 리포트 제외)

    Returns:
        list of {
          "code": str,
          "broker": str,
          "broker_country": "kr",
          "title": str,
          "report_url": str,
          "published_at": datetime,
          "target_price": int | None,
          "rating": str | None,
          "currency": "KRW",
        }
    """
    import re
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    KST = ZoneInfo("Asia/Seoul")
    base = "https://finance.naver.com/research"
    cutoff = datetime.now(tz=KST) - timedelta(days=days)

    def _soup(url: str) -> BeautifulSoup:
        r = requests.get(url, headers=HEADERS, verify=False, timeout=10)
        r.encoding = "euc-kr"
        return BeautifulSoup(r.text, "lxml")

    def _list(page: int) -> list[dict]:
        url = f"{base}/company_list.naver?searchType=itemCode&itemCode={code}&page={page}"
        soup = _soup(url)
        rows = []
        for tr in soup.select("table.type_1 tr"):
            tds = tr.select("td")
            if len(tds) < 5:
                continue
            a = tds[1].select_one("a")
            if not a:
                continue
            nid_m = re.search(r"nid=(\d+)", a.get("href", ""))
            if not nid_m:
                continue
            try:
                published = datetime.strptime(tds[4].get_text(strip=True), "%y.%m.%d").replace(tzinfo=KST)
            except (ValueError, TypeError):
                continue
            rows.append({
                "nid": int(nid_m.group(1)),
                "title": a.get_text(strip=True),
                "broker": tds[2].get_text(strip=True) or None,
                "published_at": published,
                "report_url": f"{base}/{a['href']}",
            })
        return rows

    def _normalize_rating(raw: str | None) -> str | None:
        """네이버 표기 ('매수' / 'Buy' 등) → DB enum ('buy'/'hold'/'sell'/...)."""
        if not raw:
            return None
        t = raw.strip().lower()
        if not t or t in ("없음", "n/a", "-"):
            return None
        if "strong" in t and "buy" in t or t in ("적극매수",):
            return "strong_buy"
        if "strong" in t and "sell" in t:
            return "strong_sell"
        if "buy" in t or t in ("매수", "비중확대", "마켓퍼폼", "단기매수"):
            return "buy"
        if "sell" in t or t in ("매도", "비중축소"):
            return "sell"
        if "hold" in t or t in ("보유", "중립", "neutral", "marketperform"):
            return "hold"
        return None

    def _detail(nid: int) -> dict:
        url = f"{base}/company_read.naver?nid={nid}&searchType=itemCode&itemCode={code}"
        soup = _soup(url)
        tp = None
        rating = None
        m_el = soup.select_one("em.money strong")
        if m_el:
            try:
                tp = int(m_el.get_text(strip=True).replace(",", ""))
            except ValueError:
                pass
        r_el = soup.select_one("em.coment")
        if r_el:
            rating = _normalize_rating(r_el.get_text(strip=True))
        return {"target_price": tp, "rating": rating}

    out = []
    for p in range(1, max_pages + 1):
        rows = _list(p)
        if not rows:
            break
        for row in rows:
            if row["published_at"] < cutoff:
                continue
            row.update(_detail(row["nid"]))
            row["code"] = code
            row["broker_country"] = "kr"
            row["currency"] = "KRW"
            out.append(row)
    return out


if __name__ == "__main__":
    code = "036570"
    print(f"=== {code} 펀더멘털 (네이버) ===")
    print(fetch_fundamentals(code))
    print(f"\n=== {code} 일별 시세 ===")
    print(fetch_daily(code, pages=1).head())
    print(f"\n=== {code} 리서치 리포트 (30일) ===")
    for r in fetch_research_reports(code, max_pages=1, days=30):
        print(f"  [{r['published_at']:%Y-%m-%d}] {r['broker']:12s} TP={r['target_price']} 의견={r['rating']}")
