"""
analyze_position(005930) 토큰 측정 일회성 스크립트.
output: stdout JSON only (다른 코드와 결합 X).
"""
from __future__ import annotations
import json
import sys
import time
from typing import Any

import tiktoken

from server.db import open_pool
from server.mcp.server import analyze_position, check_base_freshness


CODE = "005930"


def _bytes(o: Any) -> int:
    return len(json.dumps(o, default=str, ensure_ascii=False).encode("utf-8"))


def _ascii_bytes(o: Any) -> int:
    return len(json.dumps(o, default=str, ensure_ascii=True).encode("utf-8"))


def _tokens(o: Any, enc: tiktoken.Encoding) -> int:
    s = json.dumps(o, default=str, ensure_ascii=False)
    return len(enc.encode(s, disallowed_special=()))


def _category_breakdown(bundle: dict, enc_cl: tiktoken.Encoding, enc_o: tiktoken.Encoding) -> list[dict]:
    rows = []
    for k, v in bundle.items():
        if k in ("errors", "categories_succeeded", "categories_total", "coverage_pct", "coverage_warning"):
            continue
        rows.append({
            "category": k,
            "bytes_utf8": _bytes(v),
            "bytes_ascii": _ascii_bytes(v),
            "tokens_cl100k": _tokens(v, enc_cl),
            "tokens_o200k": _tokens(v, enc_o),
            "type": type(v).__name__,
        })
    rows.sort(key=lambda r: r["bytes_utf8"], reverse=True)
    return rows


def main() -> None:
    out: dict = {"started_at": time.time(), "code": CODE}
    open_pool()

    # 1단계: stale 조회
    t0 = time.perf_counter()
    fresh = check_base_freshness(auto_refresh=False)
    t_fresh = time.perf_counter() - t0
    out["check_base_freshness_seconds"] = round(t_fresh, 3)
    out["check_base_freshness_summary"] = fresh.get("summary", {})
    out["check_base_freshness_economy_count"] = len(fresh.get("economy", []))
    out["check_base_freshness_industries_count"] = len(fresh.get("industries", []))
    out["check_base_freshness_stocks_count"] = len(fresh.get("stocks", []))

    # 3단계: with_base
    t0 = time.perf_counter()
    r_with = analyze_position(CODE, include_base=True)
    t_with = time.perf_counter() - t0
    out["analyze_position_with_base_seconds"] = round(t_with, 3)

    # 3단계: without_base
    t0 = time.perf_counter()
    r_without = analyze_position(CODE, include_base=False)
    t_without = time.perf_counter() - t0
    out["analyze_position_without_base_seconds"] = round(t_without, 3)

    enc_cl = tiktoken.get_encoding("cl100k_base")
    enc_o = tiktoken.get_encoding("o200k_base")

    out["with_base"] = {
        "categories_succeeded": r_with.get("categories_succeeded"),
        "categories_total": r_with.get("categories_total"),
        "coverage_pct": r_with.get("coverage_pct"),
        "errors": r_with.get("errors", {}),
        "bytes_utf8": _bytes(r_with),
        "bytes_ascii": _ascii_bytes(r_with),
        "tokens_cl100k": _tokens(r_with, enc_cl),
        "tokens_o200k": _tokens(r_with, enc_o),
        "category_keys": [k for k in r_with.keys()
                          if k not in ("errors", "categories_succeeded",
                                       "categories_total", "coverage_pct",
                                       "coverage_warning")],
        "category_breakdown": _category_breakdown(r_with, enc_cl, enc_o),
    }

    out["without_base"] = {
        "categories_succeeded": r_without.get("categories_succeeded"),
        "categories_total": r_without.get("categories_total"),
        "coverage_pct": r_without.get("coverage_pct"),
        "errors": r_without.get("errors", {}),
        "bytes_utf8": _bytes(r_without),
        "bytes_ascii": _ascii_bytes(r_without),
        "tokens_cl100k": _tokens(r_without, enc_cl),
        "tokens_o200k": _tokens(r_without, enc_o),
        "category_breakdown": _category_breakdown(r_without, enc_cl, enc_o),
    }

    # base 카테고리 본문 길이 검증 (with_base 만)
    base_payload = r_with.get("base") or {}
    out["base_inspection"] = {
        "economy_keys": list((base_payload.get("economy") or {}).keys()),
        "economy_body_len": len((base_payload.get("economy") or {}).get("body") or "") if isinstance(base_payload.get("economy"), dict) else 0,
        "industry_keys": list((base_payload.get("industry") or {}).keys()) if base_payload.get("industry") else [],
        "industry_body_len": len((base_payload.get("industry") or {}).get("body") or "") if isinstance(base_payload.get("industry"), dict) else 0,
        "stock_keys": list((base_payload.get("stock") or {}).keys()) if base_payload.get("stock") else [],
        "stock_body_len": len((base_payload.get("stock") or {}).get("body") or "") if isinstance(base_payload.get("stock"), dict) else 0,
    }

    # disclosures 건수
    disc = r_with.get("disclosures") or []
    out["disclosures_inspection"] = {
        "count": len(disc) if isinstance(disc, list) else None,
        "first_keys": list(disc[0].keys()) if disc else [],
    }

    # insider_trades summary
    ins = r_with.get("insider_trades") or {}
    out["insider_inspection"] = {
        "count": ins.get("count"),
        "summary_90d": ins.get("summary_90d"),
        "first_keys": list((ins.get("rows") or [{}])[0].keys()) if ins.get("rows") else [],
    }

    # ratio
    if out["without_base"]["bytes_utf8"]:
        out["bytes_ratio_with_over_without"] = round(
            out["with_base"]["bytes_utf8"] / out["without_base"]["bytes_utf8"], 3
        )
        out["tokens_cl100k_ratio_with_over_without"] = round(
            out["with_base"]["tokens_cl100k"] / out["without_base"]["tokens_cl100k"], 3
        )

    out["finished_at"] = time.time()
    print(json.dumps(out, ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    main()
