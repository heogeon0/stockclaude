# WebSearch 가이드 (v7, 2026-05 — BLOCKING 폐지 + 단위별 LLM 자율)

> 로드 시점: per-stock-analysis 4단계 LLM 판단 / base inline 1단계 데이터 수집 / 재실행 시.
> v7 변경: **강제 호출 횟수 폐지**. 정형 MCP가 1차, WebSearch 는 정형 미커버 nuance 발견 시 LLM 자율 호출.
> 가이드 톤: 의무 X / 권장 O. 케이스별 LLM 판단.

---

## 단위별 자율 판단 가이드

### 종목 단위 (per-stock-analysis 4단계)

`analyze_position(code, include_base=True)` 응답을 본 직후 LLM 자율 평가:

| 상황 | WebSearch 권장 강도 |
|---|---|
| `disclosures` 비었고 등락률 |±1%| 미만 + 거래량 정상 + 컨센 변동 없음 | **skip OK** — 정형으로 충분 |
| `disclosures` 있는데 사유 모호 (예: "주요사항보고서" 만 있고 본문 nuance 부재) | **권장** — 매체 해석·시장 반응 |
| 실적 D-7 이내 종목 | **강력 권장** — 가이던스 톤·컨센 변경 |
| 등락률 ±3% + disclosures 부재 | **강력 권장** — 사유 추적 (외인 매매·매크로 영향 등) |
| 52주 신고가/신저가 갱신 | **권장** — 매체 해설·애널 코멘트 |
| 거래량 30일 평균 1.5배+ | **권장** — 정형 미커버 사유 |
| 외인·기관 z±2 이상 | **권장** — 의도 해석 (패시브 리밸런싱·실적 베팅 등) |

> 호출 시 표준 쿼리: `"YYYY-MM-DD {종목명} 뉴스"` (KR) / `"{ticker} {date} news earnings"` (US). 도메인 한정 옵션: `site:bloomberg.com OR site:reuters.com`.

### economy base 단위 (base-economy-update-inline)

`get_macro_indicators_us` / `get_macro_indicators_kr` / `get_yield_curve` / `get_fx_rate` / `get_economic_calendar` 결과 본 직후 LLM 자율 평가:

| 상황 | 권장 강도 |
|---|---|
| 평소 매크로 갱신 (FRED/ECOS 수치만 변동) | **skip OK** — 정형 수치만으로 OK |
| FOMC 직후 / 한은 금통위 직후 | **강력 권장** — 의장·총재 발언 톤·향후 가이던스 |
| CPI / PCE 발표 직후 (예측 vs 실제 ±0.3%p+ 괴리) | **권장** — 시장 반응 해석 |
| 환율 급변동 (DEXKOUS ±2%/주) | **권장** — 개입·자금흐름 추측 |
| 지정학 이벤트 발생 (중동·미중·우크라·제재) | **강력 권장** — 정형 자산 거의 없음 |

### industry base 단위 (base-industry-update-inline)

`compute_industry_metrics` 로 정량 메트릭 자동 산출 후 5 차원 본문 작성 시:

| 차원 | 권장 강도 |
|---|---|
| 사이클 / 점유율 / 규제 / 경쟁 / 기술 | **모두 강력 권장** — 정형 자산 거의 없음. 도메인 한정 (`Gartner OR IDC` / `site:fsc.go.kr` 등) 강력 권장. |

### stock base 단위 (base-stock-update-inline)

딜레이더 6종 카테고리 — 정형 우선 (`get_kr_disclosures` / `get_us_disclosures` / `get_kr_insider_trades` / `get_us_insider_trades` / `get_kr_major_shareholders`) → 정형 미커버 nuance 시 LLM 자율 search:

| 카테고리 | 정형 커버 | 권장 강도 |
|---|---|---|
| #1 M&A | 공시 90% | 정형 미커버 시 (루머·협상 단계) |
| #2 관계사 | 공시 60% | 비공식 보도 시 |
| #3 경쟁사 | — | **강력 권장** (정형 X) |
| #4 규제 | 공시 일부 | **강력 권장** (`site:fsc.go.kr` / `site:sec.gov`) |
| #5 주주행동주의 | insider 부분 | 행동주의 펀드 공개 캠페인 시 |
| #6 대주주 변동 | insider 90% | 정형 미커버 시 (시장 추측) |

---

## 도메인 한정 쿼리 패턴 (강력 권장)

WebSearch 호출 시 신뢰 도메인 한정으로 노이즈 감소:

```
# 매크로·발언 톤
site:cnbc.com OR site:reuters.com OR site:bloomberg.com FOMC 발언 톤 YYYY-MM
site:bok.or.kr OR site:edaily.co.kr 금통위 결정 YYYY-MM

# 규제·정책
site:fsc.go.kr OR site:fss.or.kr OR site:moef.go.kr {종목/산업} YYYY
site:sec.gov OR site:europa.eu {ticker/산업} regulation YYYY

# 산업 점유율
"YYYY {산업} 시장 점유율" Gartner OR IDC OR Counterpoint
"YYYY {industry} market share" report

# 종목 뉴스
site:bloomberg.com OR site:reuters.com OR site:wsj.com {ticker} YYYY-MM-DD
site:hankyung.com OR site:mk.co.kr {종목명} YYYY-MM-DD

# 지정학
"middle east" OR "us-china" OR "ukraine" tension YYYY-MM
중동 OR 미중 OR 제재 위험 YYYY-MM
```

---

## 재실행 / 캐시 가이드 (v7 — 강제 → 권장)

- 같은 분(分) 내 재실행: 정형 MCP / WebSearch 모두 캐시 OK
- 30분+ 차이 재실행: 정형 MCP 는 fresh 조회 권장 (가격·공시 갱신). WebSearch 는 동일 쿼리 재호출 가치 작음 (검색 결과 변화 적음)
- 실적 D-7 종목: 시즌 동안 매 분석마다 search 강력 권장 (가이던스·컨센 빠른 변화)
- NXT/시간외 가격 vs KRX 종가 ±3%+: 사유 추적용 search 권장

---

## 결과 활용

- daily 보고서 `## 뉴스 / 촉매` 섹션에 기록 (없으면 "정형 데이터로 충분 — 자율 search 미수행")
- 유의미한 팩트는 `## 📌 Base 영향도 판단` 섹션으로도 승격
- 자율 호출 패턴은 `dependency-audit-template.md` "참고 메트릭" 섹션에 기록 (v6.g)

---

## compute_signals 서버 에러 시 우회

- 지표(`compute_indicators`) + 이벤트(`detect_events`) + 등급(`compute_score`)을 조합해 **수동 verdict 산정**
- daily 보고서에 "⚠️ compute_signals 실패 — 지표 기반 수동 판정" 명시
