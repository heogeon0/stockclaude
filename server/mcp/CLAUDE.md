# server/mcp/ — MCP 툴 등록 가이드 (가장 자주 진입하는 폴더)

## 단일 파일 현실

`server/mcp/server.py`는 **4250줄, 88 `@mcp.tool` 데코레이터**가 한 파일에 모두 등록되어 있음. 분할은 §10.2 이슈로 추적 — **즉시 분할 금지**. 신규 툴은 의미상 가장 가까운 그룹의 섹션 주석 아래에 추가.

```python
# =====================================================================
# 조회 툴
# =====================================================================
```

새 툴이 어떤 그룹에도 안 어울리면 새 섹션 주석을 만든다. 위치는 파일 하단 추천 (기존 그룹 사이에 끼워 넣어 diff 충돌 키우지 말 것).

## 그룹 7개 (현 구조 + line offset)

| 그룹 | server.py 위치 | 대표 툴 |
|---|---|---|
| 조회 | 244 | `get_portfolio`, `list_daily_positions`, `get_stock_context`, `get_applied_weights`, `list_trades` |
| 분석 (deterministic) | 343 | `compute_indicators`, `compute_signals`, `check_concentration`, `propose_position_params`, `analyze_position`, `analyze_flow`, `analyze_volatility` |
| 쓰기 | 488 | `record_trade`, `save_daily_report`, `override_score_weights`, `register_stock`, `propose_watch_levels` |
| KIS 직접 호출 (Phase 3b) | 800 | `kis_current_price`, `kis_intraday`, `kis_us_quote`, `realtime_price` |
| 재무·이벤트 | 871 / 1014 | `compute_financials`, `detect_earnings_surprise_tool`, `detect_events`, `portfolio_correlation` |
| 컨센서스·애널 | 951 | `get_analyst_consensus`, `analyze_consensus_trend`, `list_analyst_reports`, `record_analyst_report`, `refresh_kr_consensus`, `refresh_us_consensus` |
| 회고·전략·룰 | 2910~ | `get_weekly_review`, `save_weekly_review`, `prepare_weekly_review_*`, `get_weekly_strategy`, `register_rule`, `update_rule`, `deprecate_rule`, `list_rule_catalog`, `propose_base_narrative_revision` |

기타: discovery (1911~), Issue #3 Tier A (2160~), 헬스체크 (4030), 정형 매크로/공시/insider (4066~).

## `@mcp.tool` 데코레이터 패턴

```python
@mcp.tool
def get_portfolio() -> dict:
    """
    docstring (Claude가 읽음 — 사용처·주의사항 명시).

    ⚠️ Pending 포지션 제외. /stock-daily 스코프는 list_daily_positions().
    """
    uid = settings.stock_user_id
    data = portfolio.compute_current_weights(uid)   # repos 경유
    return {
        "positions": [_row_safe(p) for p in data["positions"]],
        "cash": {k: float(v) for k, v in data["cash"].items()},
        ...
    }
```

규칙:
1. 첫 줄에 `uid = settings.stock_user_id` (단일 유저 fallback). API와 달리 MCP는 OAuth email→user_id 변환이 없으므로 직접 settings 참조.
2. DB 접근은 `server.repos.*`만. 직접 SQL 금지.
3. 반환은 dict 또는 list[dict]. **반드시 JSON-safe** (다음 항목).
4. docstring은 Claude의 행동 지침. 함정·사용처·다른 툴과의 차이를 명시.

## 반환 JSON-safe 강제 (research §4.10)

MCP structured output은 표준 JSON 타입만 허용. Decimal/datetime/numpy/pandas/NaN/Inf가 섞이면 outputSchema 오류.

두 헬퍼 (`server/mcp/server.py:191-240`):

- `_row_safe(row)` — dict 1단계만 평탄화. Decimal→float, datetime→isoformat.
- `_json_safe(obj)` — **재귀**. numpy(int/float/bool/ndarray) + Decimal + datetime + dict + list/tuple. NaN/Inf는 None으로.

선택 가이드:
- 단순 row 1개 → `_row_safe`.
- signal dict / 분석 결과 / 중첩 list → `_json_safe`.
- numpy scalar 가능성 있으면 무조건 `_json_safe`.

```python
return {
    "indicators": _json_safe(df_ind.to_dict()),     # 중첩·numpy
    "position": _row_safe(positions.get_position(uid, code)),  # 단순 row
}
```

## docstring ⚠️ 컨벤션

함정은 docstring에 **⚠️ 이모지**로 명시. Claude가 docstring을 우선 읽고 행동을 정함.

```python
"""
현재 유저의 전체 포트폴리오 (Active 포지션·현금·실현이익).
KR/US 분리 집계, 환율 미적용 (Claude가 필요시 변환).

⚠️ Pending(감시 대기) 포지션은 제외됨. /stock-daily 스코프는 `list_daily_positions()` 사용.
"""
```

(`server/mcp/server.py:248-254` 인용.)

명시 대상: Pending 제외, KR/US 단위 차이, 환율 미적용, KIS 한도, fallback 경로, 다른 툴 권장 등.

## Pending vs Active (research §4.4)

- `get_portfolio()` — Active만. `positions.compute_current_weights(uid)` 기반.
- `list_daily_positions()` — Active + Pending. `positions.list_daily_scope(uid)` 기반. all_codes 일괄 반환.
- **함정**: daily 워크플로우에서 `get_portfolio` 쓰면 Pending 종목이 누락된다. 반드시 `list_daily_positions` (server/mcp/server.py:271-301).
- 신규 분석 툴이 "전체 포지션 일괄 처리" 의미라면 `list_daily_scope` 또는 `positions.list_all(uid)` 사용.

## KR/US ticker 자동 판정 (research §4.5)

`_is_us_ticker(code)` (server/mcp/server.py:127-129): **6자리 숫자 = KR**, 그 외 = US.

```python
def _is_us_ticker(code: str) -> bool:
    return not (code.isdigit() and len(code) == 6)
```

함정: KOSDAQ(091990 등)도 6자리 숫자라 KR로 분류 — 정상. 알파벳·숫자 혼합 6자리 US ticker가 만약 존재하면 잘못 분류 가능 (현재까진 미발견). 신규 시장 추가 시 이 함수 다시 확인.

## KIS 100/150 fallback + 한글 컬럼 (research §4.2)

`_fetch_ohlcv(code, days)` (server/mcp/server.py:132-182):

- KR + days ≤ 150 → `kis.fetch_period_ohlcv` (공식·안정).
- KR + days > 150 또는 KIS 실패 → `naver.fetch_daily` (스크래핑).
- US + days ≤ 100 → `kis.fetch_us_daily`.
- US + days > 100 또는 KIS 실패 → `yfinance` period 매핑 (1mo/3mo/6mo/1y/2y/5y).

모든 source가 **한글 컬럼**으로 normalize: `날짜/시가/고가/저가/종가/거래량`. 새 source 추가 시 변환 layer 의무.

함정: KIS 실패는 silent fallback. 디버깅 시 어느 경로 탔는지 안 보이므로 신규 코드는 로그 명시 권장.

## 통화 미변환 룰 (research §4.3)

MCP는 **unconverted** 반환. KR=KRW, US=USD 그대로. 환율 변환은 API 라우터 또는 Claude 본문 추론에서.

- `stocks.currency` ∈ ('KRW','USD') CHECK.
- `cash_balance`도 currency별 별도 행.
- 합산 응답이 필요하면 dict 키에 `kr_total_krw`, `us_total_usd`처럼 단위 명시.

함정: 무심코 KR+US 합산하면 단위 섞임. SKILL.md에 "환율 미적용, Claude가 필요 시 변환" 명시됨 (server/mcp/server.py:251).

## KST 분기 (research §4.1)

- `_kr_market_state()` (server/mcp/server.py:812) — KST 정규장/시간외/마감 판정.
- SQL 거래일 비교는 항상 `(executed_at AT TIME ZONE 'Asia/Seoul')::date` (server/mcp/server.py:3311, 3434, 3446, 3689).
- `datetime.now()` 그대로 쓰지 말고 `ZoneInfo("Asia/Seoul")` 명시.
- 공시 published_at은 naive datetime이면 KST로 강제 부착 (analysis/events.py).

신규 SQL 작성 시 거래일 분기는 무조건 AT TIME ZONE 'Asia/Seoul'.

## stdio vs streamable-http 분기

`_build_mcp()` (server/mcp/server.py:88-121):

- `settings.mcp_remote_enabled` False (default) → `FastMCP("stock-manager")` 무인증 stdio.
- True → `MCP_BASE_URL` + `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` + `ALLOWED_EMAILS` 모두 필수, 누락 시 RuntimeError. `server/mcp/auth.py`의 GoogleProvider 사용.

신규 툴은 두 모드에서 동일하게 동작해야 함 — auth 분기 안에서 다른 동작 만들지 말 것.

## 합성 점수·셀·is_stale 재제안 금지 (research §4.7, §6.1)

라운드 2026-05-stock-daily-overhaul에서 **합성 점수·매트릭스·decision-tree·position-action-rules·12셀 매트릭스·base-*-updater 서브에이전트**가 모두 폐기됨.

- `analyze_position`은 raw 9 카테고리만. 점수 통합 X.
- `references/_archive/`에 폐기본 보존 (decision-tree, scoring-weights, position-action-rules) — 재제안 차단 목적.
- 대체: master-principles 거장 10원칙 + `industries.avg_per/avg_pbr/avg_roe/avg_op_margin/vol_baseline_30d` 대비 본문 판단.

**함정**: Claude가 점수 다시 추가하거나 셀 룩업 부활시키려는 경향 강함. 신규 툴이 verdict/grade를 단일 합성값으로 반환하면 거부.

## rule_catalog는 DB SSoT (research §5.5)

매매 룰은 `rule_catalog` 테이블이 SSoT. 신규 룰 추가는 `register_rule` MCP 툴 경유. markdown reference의 룰 텍스트만 보고 판단 X.

회고 시 `list_rule_catalog`로 룰별 win-rate 자동 분류 (라운드 2026-05-weekly-review).

## 신규 툴 추가 체크리스트

1. **그룹 결정** — 위 7 그룹 중 가장 가까운 곳. 애매하면 분석 (deterministic) 또는 조회.
2. **데코레이터** — `@mcp.tool` + 타입 힌트 + 한국어 docstring + 함정 ⚠️.
3. **uid 주입** — `uid = settings.stock_user_id` 첫 줄.
4. **repos 경유** — `from server.repos import <module>` 사용. 직접 SQL 금지.
5. **반환 JSON-safe** — `_row_safe` 또는 `_json_safe`. numpy/Decimal/datetime/NaN/Inf 가능성 점검.
6. **docstring ⚠️** — Pending 제외, KR/US 단위, KIS 한도, 환율 미적용 등 함정 명시.
7. **SKILL.md 인벤토리 갱신** (선택) — 새 툴이 daily/discover/research 워크플로우에 들어가면 `.claude/skills/stock/SKILL.md`의 89 툴 인벤토리 업데이트.
8. **라운드 doc 영향 검토** — 합성 점수/매트릭스/decision-tree 부활 아닌지 자가검증. 폐기 항목과 충돌하면 STOP.

## 폴더 구조

```
server/mcp/
├── server.py    4250줄 — 88 @mcp.tool + 헬퍼 (_fetch_ohlcv / _is_us_ticker / _row_safe / _json_safe / _kr_market_state)
├── auth.py      streamable-http 모드용 GoogleProvider OAuth proxy
└── __init__.py
```

분할 시 권장 (§10.2 이슈에서 다룸): `tools/{queries,analysis,writes,market,financials,consensus,review_strategy}.py`로 그룹별 분리, `server.py`는 import + FastMCP 등록만 보유. 즉시 작업 X.
