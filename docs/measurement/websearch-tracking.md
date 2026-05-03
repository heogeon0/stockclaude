# WebSearch 호출 카운트 측정

stock skill **v8.b** 부터 운영. WebSearch 의존도 감축 (도입 전 추정 17~50회/일 → 도입 후 1주 평균) 정량 비교용 인프라.

## 1. 로그 파일

- 경로: `agent/_search_log.jsonl` (이 디렉토리 자체가 `.gitignore` — **commit 금지**)
- 포맷: JSONL (1줄 = 1 호출)
- append-only — LLM 이 WebSearch 를 호출할 때마다 1줄씩 추가

## 2. 1줄 스키마

| 필드 | 타입 | 예시 | 설명 |
|---|---|---|---|
| `date` | string (`YYYY-MM-DD`) | `"2026-05-03"` | ISO 날짜 |
| `timestamp` | string (ISO 8601) | `"2026-05-03T09:30:15+09:00"` | 호출 시각 (TZ 포함) |
| `scope` | enum | `"stock"` | `stock` / `economy_base` / `industry_base` / `stock_base` / `macro` |
| `code_or_market` | string | `"005930"` / `"kr"` / `"semiconductor"` | 종목 코드 / 시장 / 산업 코드 |
| `trigger` | string | `"earnings_d7"` | `manual` / `stale_disclosures_empty` / `stale_in_industry_5dim` / `earnings_d7` / `52w_break` / ... (오픈셋) |
| `query` | string | `"삼성전자 1Q 가이던스"` | 실제 WebSearch 쿼리 |
| `cached` | bool | `false` | 같은 분 내 동일 쿼리 재사용이면 `true` |

7개 필드 **모두 필수** — 누락된 row 는 집계 시 skip 처리.

### 예시 (1줄)

```json
{"date":"2026-05-03","timestamp":"2026-05-03T09:30:15+09:00","scope":"stock","code_or_market":"005930","trigger":"earnings_d7","query":"삼성전자 1Q 가이던스","cached":false}
```

## 3. 집계 명령

```bash
# default: agent/_search_log.jsonl, 최근 7일, scope 별 분포
python scripts/measure_websearch.py

# 14일 윈도, trigger 별 분포
python scripts/measure_websearch.py --days 14 --by trigger

# 다른 경로
python scripts/measure_websearch.py --input path/to/log.jsonl --days 30 --by scope
```

CLI 인자:

| 인자 | 기본값 | 설명 |
|---|---|---|
| `--input` | `agent/_search_log.jsonl` | jsonl 경로 |
| `--days` | `7` | 집계 윈도 (anchor = log 내 max(date)) |
| `--by` | `scope` | 분포 표 그룹키 (`scope` / `trigger`) |

stdlib (argparse + json + collections + datetime) 만 사용 — 외부 의존성 추가 X.

## 4. 출력 예시

```
============================================================
WebSearch 호출 집계
============================================================
input  : agent/_search_log.jsonl
window : last 7 day(s) (anchor = max(date) in log)
rows   : 35  (skipped malformed: 0)
avg/day: 5.00
cached : 14.3%

## Baseline 비교 (운영 전 추정 17~50회/일)
  vs 17/day  →  reduction  +70.6%
  vs 50/day  →  reduction  +90.0%

## 일별 호출 수
  2026-04-27     6  ( 17.1%)
  2026-04-28     5  ( 14.3%)
  ...

## scope 별 분포
  stock              18  ( 51.4%)
  industry_base       8  ( 22.9%)
  economy_base        5  ( 14.3%)
  stock_base          3  (  8.6%)
  macro               1  (  2.9%)
```

`reduction` 양수=감축, 음수=baseline 초과.

## 5. 운영 가이드 (LLM 용)

WebSearch 호출 직후 (즉시) 1줄 append:

1. `scope` — 어느 워크플로우 단위에서 호출했는지 (stock 1건 분석이면 `"stock"`)
2. `code_or_market` — 분석 대상 식별자
3. `trigger` — **왜** 이 호출이 필요했는지 (manual = 사용자 명시 요청 / 나머지 = 자동 트리거 사유)
4. `cached` — 같은 분(`HH:MM`) 내 동일 query 가 이미 있으면 `true`, 아니면 `false`

trigger 명명 가이드 (오픈셋이지만 일관성 유지):

- `manual` — 사용자 직접 요청
- `stale_disclosures_empty` — 공시 데이터 비어 있어 보강
- `stale_in_industry_5dim` — 산업 5차원 지표 stale
- `earnings_d7` — 실적 발표 D-7 이내
- `52w_break` — 52주 신고/신저 돌파
- 기타 — `<sensor>_<reason>` 형태로 신설 가능

## 6. 테스트

```bash
pytest tests/test_measure_websearch.py
```

합성 jsonl 7 row + malformed 케이스 + CLI smoke 16개 테스트.
