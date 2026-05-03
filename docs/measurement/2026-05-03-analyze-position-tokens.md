# `analyze_position` 토큰 측정 (2026-05-03)

## 0. 측정 환경

| 항목 | 값 |
|---|---|
| commit (직전) | `64329a5` (refactor: per-stock 7→5 단순화) |
| 비교 베이스 | `a364c35` (analyze_position v4 12 카테고리 도입) |
| 측정 시각 | 2026-05-03 KST (KR 정규장 외, naver realtime 분기) |
| 측정 종목 | `005930` (삼성전자, KR) |
| Python | 3.14.4 (`uv run`) |
| tiktoken | 0.12.0 (`cl100k_base` / `o200k_base`) |
| DB | PostgreSQL pool open (실 데이터, mocking 없음) |
| 외부 API | KIS / Naver / DART / Finnhub key 모두 활성. FRED key 의존 카테고리는 본 호출 경로에 없음 |
| Driver script | `docs/measurement/measure_analyze_position.py` (측정 전용, 기존 함수 호출만) |
| Raw 결과 | `docs/measurement/2026-05-03-raw.json` |

## 1. 새 5단계 워크플로우 실호출 결과

per-stock-analysis.md 5단계 (`stock-daily` 단순화 직후) 의 1·3 단계만 실호출:

| 단계 | MCP | 시간 | 비고 |
|---|---|---|---|
| 1 | `check_base_freshness(auto_refresh=False)` | **34.5 s** | 13 stocks + 10 industries + 2 economy 만기 일괄 조회. 6건 stale 감지 → `auto_triggers` 6 (us economy + 5 industries) |
| 2 | (LLM 인라인 절차) | — | 본 데모 skip. inline procedure 만 권장 |
| 3a | `analyze_position("005930", include_base=True)` | **15.4 s** | coverage 100% (12/12), errors `{}` |
| 3b | `analyze_position("005930", include_base=False)` | **12.6 s** | coverage 100% (11/11), errors `{}` |

## 2. 응답 크기 / 토큰

`json.dumps(default=str, ensure_ascii=False)` 직렬화 기준.

| 모드 | bytes UTF-8 | bytes ASCII (`\uXXXX`) | tokens cl100k | tokens o200k |
|---|---:|---:|---:|---:|
| `include_base=True` | **61,426** | 89,079 | **28,510** | **23,292** |
| `include_base=False` | 34,828 | 48,644 | 15,891 | 13,255 |
| **ratio** | **1.764×** | 1.831× | **1.794×** | 1.757× |

> ASCII 직렬화는 한글이 `\uXXXX` 6 byte 로 부풀려져 byte/token 비율이 왜곡된다 — 본 보고서는 UTF-8 byte 와 토큰을 1차 지표로 사용한다.

## 3. 카테고리별 byte/token 분포 (`include_base=True`)

| # | 카테고리 | bytes | % | cl100k | o200k | 비고 |
|--:|---|---:|---:|---:|---:|---|
| 1 | **base** | 26,588 | **43.3%** | 12,616 | 10,034 | economy + industry + stock_base 3층 (stock_base.`content` 5,283 char 차지가 지배) |
| 2 | **context** | 26,072 | **42.4%** | 12,024 | 9,844 | stock + **base** + latest_daily + position + watch_levels — 내부에 `stock_base` 가 또 포함 (§4 중복 발견) |
| 3 | disclosures | 2,541 | 4.1% | 1,027 | 919 | DART raw 10 row (`corp_code`, `report_nm`, `rcept_no`, …) |
| 4 | signals | 2,251 | 3.7% | 1,093 | 847 | 12 전략 + summary |
| 5 | financials | 1,025 | 1.7% | 545 | 479 | DART ratios + growth + raw_summary |
| 6 | indicators | 625 | 1.0% | 311 | 282 | 12 지표 last row |
| 7 | consensus | 617 | 1.0% | 244 | 245 | view + tp_trend + rating_wave |
| 8 | flow | 486 | 0.8% | 216 | 210 | KR 기관/외인 z-score |
| 9 | realtime | 318 | 0.5% | 115 | 115 | 현재가 (Naver 분기) |
| 10 | events | 308 | 0.5% | 119 | 119 | earnings + 52w + ratings |
| 11 | volatility | 176 | 0.3% | 69 | 69 | RV/PV/regime/DD |
| 12 | insider_trades | 74 | 0.1% | 30 | 30 | KR 분기, **rows=0** (90일 cutoff) → summary 만 |
| ─ | code/name/market 등 | 26 | 0.0% | 14 | 12 | 메타 |

상위 2 카테고리(`base` + `context`) 가 **전체의 85.7%** 를 차지.

## 4. 부수 발견 — `context.base` 와 `base.stock` 100% 중복 ⚠️

`include_base=True` 호출 결과를 직접 비교:

```
context.base.content len: 5283
base.stock.content   len: 5283
IDENTICAL: True
```

코드 위치:
- `server/mcp/server.py:2618` — `bundle["context"]["base"] = stock_base.get_base(code)` (조건 없음)
- `server/mcp/server.py:2873` — `bundle["base"]["stock"] = stock_base.get_base(code)` (`include_base=True` 시)

`include_base=True` 인 호출 (per-stock-analysis 의 표준 경로) 에서 stock_base 본문이 **두 번 들어가는** 상태. 영향:

- 6,675 bytes (= 18,464 → 11,789, 단일 측정 기준) 가 매 종목마다 중복 송출.
- 5,283 char × 약 ¼ token/char ≈ **2,500–3,000 cl100k 토큰 / 종목**.
- 10 종목 daily run 기준 약 **25K–30K 토큰** 의 순수 낭비. 별도 후속 PR 권장.

> 본 PR(measurement-only) 에서는 코드 수정 X — 단순 보고. 후속 issue 가 필요하다고 판단되면 PM 수동 등록 (직접 issue create 금지 규약).

## 5. prompt cache 활용 가설 (10 종목 daily 기준)

Anthropic prompt cache 는 동일 prefix 가 ≥1024 토큰 이상이면 cache_control 로 hit. 10 종목 분석 1 사이클을 가정하면:

| 부분 | 종목당 cl100k | 10 종목 합 | 캐시 가능성 | 절감 가설 |
|---|---:|---:|---|---:|
| `base.economy` (1 시장) | ~1,500 | 15,000 | **9 hit / 10** (kr 만 사용 가정) | -13,500 |
| `base.industry` (1 산업) | ~3,500 | 35,000 | 평균 2–3 산업 → **6–7 hit** | -21,000 ~ -24,500 |
| `base.stock` (종목별) | ~7,500 | 75,000 | 종목별 상이 → **0 hit** | 0 |
| `context` (실시간/포지션 포함) | ~12,000 | 120,000 | 매번 다름 → **0 hit** | 0 |
| 그 외 raw (signals/disclosures/…) | ~3,500 | 35,000 | 매번 다름 → **0 hit** | 0 |
| **합계** | **~28,000** | **280,000** | — | **약 -34K ~ -38K (12–14%)** |

캐시 적용 전제: economy / industry payload 를 시스템 프롬프트 prefix 로 분리하고 cache_control breakpoint 를 끼울 때 한정. 현재처럼 `analyze_position` 응답 1덩이로 받으면 cache 가 종목별로 prefix 분기 → hit 0.

따라서 토큰 절감이 목표라면 **§4 의 중복 제거가 우선** (즉시 -25K~30K, 코드 1줄 수정), prompt-cache 분리는 더 큰 작업이지만 추가 -34K 가능.

## 6. 권장 조치 (트레이드오프)

| 옵션 | 토큰 효과 (10 종목/일) | 코드 변경 | 위험 | 권장 |
|---|---:|---|---|---|
| A. 현 default 유지 | 0 | 0 | 0 | × |
| B. `include_base=True` 시 `context.base` 제거 (중복 제거) | **-25K ~ -30K** | `analyze_position` 1 분기 추가 | per-stock-analysis 가이드/sub-agent 가 `context.base` 키 직접 참조 시 깨짐 → grep 1회 | **○ (즉시 후속 PR)** |
| C. `include_base=False` 를 default 로 회귀 + base 별도 호출 옵션 | -38K (50% 절감) | skill / sub-agent 절차 모두 영향 | per-stock-analysis 5 단계 단순화 직후 → 다시 단계 늘어남 | △ (논의 필요) |
| D. economy/industry 만 시스템 프롬프트 prefix 로 분리 + cache_control | 추가 -34K | client 측 (skill) 변경 | base 갱신 직후 cache miss 1회 | ○ (B 이후 검토) |

**현 시점 결정 권고**: **B 단독**. C/D 는 stock-daily 절차 안정화 후 별도 measure 사이클로.

## 7. (참고) v8.b WebSearch baseline 측정 가이드

skill 가이드가 **`per-stock-analysis` 단위별 LLM 자율 가이드** 로 전환된 후의 추가 측정용 메모.

수집 항목 (per-stock 회당):
- WebSearch 호출 횟수 (`tool_use` count, role=assistant)
- WebSearch input/output 토큰 (anthropic 응답 `usage.cache_*` + `tool_use.input` length)
- 호출 → 결정 변경 여부 (LLM 본문에 `WebSearch 결과: …` 후 매수/관망/매도 변경 추적)

로그 형식 (jsonl, 한 줄/호출):
```json
{
  "ts": "2026-05-03T09:00:00+09:00",
  "code": "005930",
  "stage": "context_check | event_window | confirm",
  "query": "...",
  "results_count": N,
  "tokens_in": K,
  "tokens_out": K,
  "decision_before": "관망",
  "decision_after": "관망",
  "changed": false
}
```

저장 위치: `docs/measurement/websearch/YYYY-MM-DD-<run-id>.jsonl`

비교 baseline: 본 보고서의 `analyze_position` 단일 응답 토큰 (28.5K cl100k / 23.3K o200k) 을 "WebSearch 0회" 케이스로 잡고, 추가 호출 1건당 평균 토큰 증분을 누적.

## 8. 핵심 수치 요약

| metric | value |
|---|---|
| `analyze_position` with_base | **61,426 B / 28,510 cl100k tokens / 23,292 o200k tokens** |
| `analyze_position` without_base | 34,828 B / 15,891 cl100k tokens / 13,255 o200k tokens |
| **with/without ratio** | **1.764× (bytes), 1.794× (cl100k)** |
| 최대 카테고리 | `base` (43.3%) + `context` (42.4%) = **85.7%** |
| 신규 발견 (중복) | `context.base` ≡ `base.stock` (5,283 char 100% identical) |
| 즉시 절감 가능 (옵션 B) | **-25K ~ -30K tokens / 10종목 daily** |
