"""
재무 기준 갱신 배치 (분기별 실행).

각 KR 종목에 대해:
  1. DART 재무제표 수집 (summarize_financials)
  2. compute_financial_ratios + growth + score
  3. stock_base 컬럼(per/pbr/roe/op_margin/...) 갱신

실행:
  uv run python -m server.jobs.refresh_base
  uv run python -m server.jobs.refresh_base --codes 000660,005930
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal

from server.analysis.financials import (
    compute_financial_ratios,
    compute_financial_score,
    compute_growth_rates,
    summarize_health,
)
from server.config import settings
from server.db import open_pool
from server.repos import positions, stock_base, stocks
from server.scrapers import dart


def _to_dec(v) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except Exception:
        return None


def refresh_code(code: str) -> dict:
    stock = stocks.get_stock(code)
    if not stock:
        return {"ok": False, "error": "stock not found"}
    if stock["market"] != "kr":
        return {"ok": False, "skipped": "US (DART 미지원)"}

    try:
        fin = dart.fetch_financials(code, years=3)
        summary = dart.summarize_financials(fin)
    except Exception as e:
        return {"ok": False, "error": f"DART 실패: {e}"}

    if not summary:
        return {"ok": False, "error": "empty summary"}

    # DART summary 는 이미 ROE / 영업이익률 / 부채비율 등을 계산해서 반환.
    # compute_financial_ratios 는 raw 값(매출/순이익/자본 등)으로 재계산하는데
    # DART summary 키와 맞지 않아 다 None → score 항상 50 으로 빠짐.
    # 그래서 summary 의 사전계산 값을 그대로 ratios dict 에 매핑.
    ratios: dict[str, float | None] = {
        "per": summary.get("PER"),
        "pbr": summary.get("PBR"),
        "eps": summary.get("EPS"),
        "bps": summary.get("BPS"),
        "psr": None,
        "ev_ebitda": None,
        "roe": summary.get("ROE"),
        "roa": summary.get("ROA"),
        "op_margin": summary.get("영업이익률"),
        "net_margin": summary.get("순이익률"),
        "debt_ratio": summary.get("부채비율"),
        "fcf_yield": None,
    }
    # YoY 성장률은 summary 에 직접 박혀있음 (quarterly 가 비어있을 수 있음).
    growth: dict[str, float | None] = {
        "revenue_yoy": summary.get("매출_YoY"),
        "op_profit_yoy": summary.get("영업이익_YoY"),
        "net_profit_yoy": summary.get("순이익_YoY"),
        "revenue_qoq": None,
        "op_profit_qoq": None,
        "eps_yoy": None,
    }
    if summary.get("quarterly"):
        # quarterly 데이터 있으면 보강
        q_growth = compute_growth_rates(summary["quarterly"])
        for k, v in q_growth.items():
            if v is not None:
                growth[k] = v
    score = compute_financial_score(ratios, growth)
    health = summarize_health(ratios, growth, score)

    stock_base.upsert_base(
        code=code,
        financial_score=score,
        per=_to_dec(ratios.get("per")),
        pbr=_to_dec(ratios.get("pbr")),
        roe=_to_dec(ratios.get("roe")),
        op_margin=_to_dec(ratios.get("op_margin")),
        fundamentals_extra={
            "growth": growth,
            "health_summary": health,
            "raw_summary_keys": list(summary.keys())[:10],
        },
    )

    return {
        "ok": True,
        "code": code,
        "financial_score": score,
        "per": ratios.get("per"),
        "roe": ratios.get("roe"),
        "op_margin": ratios.get("op_margin"),
    }


def run(codes: list[str] | None = None, *, verbose: bool = True) -> dict:
    """
    인자:
      codes: KR 종목 코드 리스트. None 시 daily-scope (Active + Pending) 전체.
      verbose: True 면 stdout에 진행 출력. MCP 호출 시는 False.

    반환:
      {"ok": [...], "skip": [...], "fail": [...], "details": {code: result}}
    """
    uid = settings.default_user_id
    if codes is None:
        scope = positions.list_daily_scope(uid)
        codes = [p["code"] for p in scope if p.get("market") == "kr"]

    results: dict = {"ok": [], "skip": [], "fail": [], "details": {}}
    for code in codes:
        r = refresh_code(code)
        results["details"][code] = r
        if r.get("ok"):
            if verbose:
                print(f"[ok]   {code} score={r['financial_score']} PER={r.get('per')} ROE={r.get('roe')}")
            results["ok"].append(code)
        elif r.get("skipped"):
            if verbose:
                print(f"[skip] {code} {r['skipped']}")
            results["skip"].append(code)
        else:
            if verbose:
                print(f"[fail] {code} {r.get('error')}")
            results["fail"].append(code)
    return results


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--codes", help="comma-separated")
    args = p.parse_args()

    open_pool()
    codes = args.codes.split(",") if args.codes else None
    r = run(codes=codes)
    print(f"\n== summary == ok={len(r['ok'])} skip={len(r['skip'])} fail={len(r['fail'])}")
    if r["fail"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
