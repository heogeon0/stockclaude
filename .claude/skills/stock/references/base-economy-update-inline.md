# base-economy-update — inline 절차

> **stale economy_base 발견 시 메인 에이전트가 직접 수행하는 절차.**
> 옛 `agents/base-economy-updater.md` (sub-agent) 폐기 → multi-device (mobile/Desktop/iOS Custom Connector) 운영 호환을 위해 inline 화.
>
> **단일 책임**: `economy_base` 행 (KR 또는 US) 본문 재작성 + 메타 7키 + DB 저장 + read-back.
> **언제**: `check_base_freshness` 결과 `economy.is_stale=true` 또는 사용자 `/base-economy --kr|--us` 호출 시.
> **누가**: stock skill 메인 LLM. sub-agent spawn 금지.

---

## 입력 인자

```
market: "kr" | "us"
```

## 0단계 — 의존성 / 진입 가드

- **다른 작업 중 inline 진입 시**: 직전 분석 결과 (다른 종목/포트폴리오 등) 를 economy 본문에 인용하지 않음. **깨끗한 상태로 10 섹션을 처음부터 작성 (Frontmatter + 8 본문 + Daily Facts — v4 시나리오 트리/사이클 단계 포함)**.
- **정형 MCP 우선** — 1단계 표의 "MCP" 컬럼이 1차 소스. WebSearch 는 정형 미커버 nuance(발언 톤·지정학·시장 해석) 발견 시 LLM 자율 호출.
- 본 절차 진행 중 daily/research 본문에 매크로 결과를 추가 inline 작성하지 말 것 (저장 후 daily 가 `get_economy_base` 로 다시 읽음).

---

## 1단계 — 데이터 수집

**정형 MCP 우선, WebSearch 는 보조** — v1 신규 4 정형 매크로 툴이 수치 부분 90%+ 커버.

| 차원 | 정형 MCP (1차) | WebSearch 권장 시점 (보조) |
|---|---|---|
| 금리 (KR) | `get_macro_indicators_kr(["722Y001"])` (한국은행 기준금리) | 금통위 직후 발언 톤·향후 가이던스 시 |
| 금리 (US) | `get_macro_indicators_us(["DFF","DGS10","DGS2","DGS3MO"])` + `get_yield_curve()` | FOMC 직후 의장 기자회견 톤 시 |
| 환율 | `get_fx_rate(pair="DEXKOUS")` (FRED) + KR 추가 시 `get_macro_indicators_kr(["731Y004"])` | 급변동 시 사유(개입·자금흐름) 추측 |
| 물가 (US/KR) | `get_macro_indicators_us(["CPIAUCSL"])` / `get_macro_indicators_kr(["901Y009"])` | 발표 직후 시장 반응 해석 |
| 경기·매크로 이벤트 | `detect_market_regime` + `get_economic_calendar(country=...)` (Finnhub) | — (정형 충분) |
| 외국인 수급 (KR) | `analyze_flow` (포트 종목) + KR 통계 (`get_macro_indicators_kr`) | 월/주 추세 해석 시 |
| 지정학 | — (정형 자산 거의 없음) | **WebSearch 권장** — 중동·미중·제재·무역 |
| 섹터 | `get_industry(code)` 종합 | — |

WebSearch 권장 쿼리 (자율 판단 — 도메인 한정 권장):
```
site:cnbc.com OR site:reuters.com FOMC 발언 톤 YYYY-MM
site:bok.or.kr OR site:edaily.co.kr 금통위 결정 YYYY-MM
"한반도 OR 중동 OR 미중" 지정학 위험 YYYY-MM-DD
```

> 강제 호출 횟수 X — 정형으로 답이 나오는 차원은 search skip OK. 발언 톤·지정학 등 정형 미커버 영역만 자율 호출.

---

## 2단계 — 본문 재작성 (10 섹션 — v4 시나리오 트리/사이클 단계 포함)

표준 템플릿: → `~/.claude/skills/stock/assets/economy-base-template.md` (있다면) 참조. 없으면 아래 구조 그대로.

base 본문 구조:
1. **Frontmatter** (메타데이터 7키 + cycle_phase + scenario_probs — 4단계 참조)
2. 금리/유동성
3. 환율/무역
4. 경기/지수
5. 지정학
6. 섹터 포지셔닝
7. (옵션) 외국인 수급 추이
8. ⭐ **시나리오 트리 (Bull / Base / Bear)** ← v4-a 신설
   - 3 시나리오 의무 작성. 각 시나리오마다:
     - 트리거 조건 (예: "FOMC 추가 인하 + CPI < 3.0%")
     - 핵심 변수 임계 (금리 / 환율 / 외인 수급)
     - 자산 배분 함의 (위험자산 비중 / 섹터 가이드)
   - 시나리오 확률 가중치 — 디폴트 Bull 25% / Base 50% / Bear 25%
   - 갱신 트리거: 어느 시나리오 확률이 ±10%p 이상 이동하면 본문 재작성
9. ⭐ **사이클 단계 (확장 / 정점 / 수축 / 저점)** ← v4-b 신설
   - 4단계 중 1개 명시 + 근거 메트릭 3개 (금리·실업·CPI 등)
   - 다음 단계 전환 트리거 (예: "10년물 - 2년물 역전 → 정점 → 수축 신호")
   - 단계별 권장 섹터 한 줄 가이드 (확장=경기민감, 정점=가치/방어, 수축=방어, 저점=경기민감 진입)
10. **📝 Daily Appended Facts (since last full review)** — 통합 후 비움

---

## 3단계 — Daily Appended Facts 통합

기존 `📝 Daily Appended Facts` 섹션 처리:

1. 분류 별 (high / medium / review_needed) 묶기
2. **high** → 본문 해당 섹션 반영
   - 금리 정책 변화 → 금리 섹션 갱신
   - 환율 레짐 전환 → 환율 섹션 갱신
3. **medium** → 추세 / 누적 변화 반영
4. **review_needed** → 섹터 포지셔닝 재검토 명시
5. 통합 후 섹션 비움 + last full review 날짜 갱신

영향도 분류 룰: → `~/.claude/skills/stock/references/economy-base-classification.md`.

---

## 4단계 — 메타 7키 + cycle_phase + scenario_probs + 저장

`save_economy_base(market, content, context, cycle_phase, scenario_probs)` 의 인자:

```python
context = {  # 메타 7키
    '금리_환경': '동결' | '인상' | '인하',
    '환율_수혜': '원화강세' | '원화약세' | '중립',
    '경기_사이클': '확장' | '회복' | '둔화' | '침체',
    '유동성': '풍부' | '중립' | '부족',
    '지정학': '안정' | '긴장' | '위기',
    '외국인_수급': '순유입' | '중립' | '순유출',
    'VI_수준': '낮음' | '중간' | '높음',
}

cycle_phase = '확장' | '정점' | '수축' | '저점'   # v4-b 신규 (DB 컬럼)

scenario_probs = {                                  # v4-a 신규 (DB 컬럼)
    'bull': 0.25,
    'base': 0.50,
    'bear': 0.25,
}
```

호출:
```python
save_economy_base(
    market=...,                # "kr" | "us"
    content=<10 섹션 본문>,     # frontmatter 포함, 시나리오 트리 + 사이클 단계 포함
    context=<7키>,
    cycle_phase=<1개>,
    scenario_probs=<dict>,
)
```

---

## 5단계 — Read-back 검증 (Trust but verify)

저장 직후:
```python
result = get_economy_base(market=...)
assert result['updated_at'] > <save 호출 직전 시각>
```

`updated_at` 이 갱신 안 되었거나 본문이 누락이면 **즉시 사용자 보고 + 재시도**.

---

## (옵션) economy daily 자동 생성

`reports/economy/{YYYY-MM-DD}.md` 가 없으면 별도 생성 가능:
- 템플릿: `~/.claude/skills/stock/assets/economy-daily-template.md`
- 4 섹션: 시장 지수 / 외국인 수급 / 주요 이벤트 / 종목별 영향
- 마지막 `📌 Economy Base 영향도 판단` 섹션

> 본 절차의 핵심 결과물은 `economy_base` (DB) 임. daily 파일은 부속.

---

## 작성 원칙

- 모든 숫자는 출처 + 시점 명시 (예: "FOMC 3/18: 3.50~3.75% 동결")
- `[실제]` / `[추정]` / `[가정]` 태깅
- WebSearch 결과 인용은 출처 URL 또는 매체 명시
- 매일 갱신 — 캐시 재사용 금지

---

## ✅ 완료 체크리스트

- [ ] 10 섹션 (Frontmatter + 시나리오 트리 + 사이클 단계 포함) 모두 작성
- [ ] 메타 7키 모두 채움 (None/공백 금지)
- [ ] `cycle_phase` 1개 명시 (확장/정점/수축/저점)
- [ ] `scenario_probs` 3 시나리오 합 = 1.0
- [ ] `save_economy_base(market, content, context, cycle_phase, scenario_probs)` 호출 성공
- [ ] `get_economy_base(market)` read-back 으로 `updated_at` 갱신 + cycle_phase / scenario_probs 일치 확인
- [ ] Daily Appended Facts 비움 + last full review 날짜 갱신

## 완료 시 메인이 정리할 것

작업 후 메인이 1~3줄로 핵심 변경 요약 (사용자에게 보고 또는 daily 본문 인용용):
```
✅ economy_base[market=kr] 갱신 (updated_at=YYYY-MM-DDTHH:MM)
주요 변경:
  - FOMC 동결 (3.50~3.75% 유지) — Daily Appended Facts → 본문 통합
  - USD/KRW 1,420 → 1,395 (원화강세 전환) — 환율_수혜 메타 변경
  - 외국인 4월 누적 +2.3조원 순유입 → 섹터 포지셔닝 반도체 OW
```

실패 시:
```
❌ economy_base[market=kr] 갱신 실패
원인: <구체 에러>
재시도 권장: <조치>
```

---

> **inline 진입 시 주의 (재강조)**: 메인이 다른 작업 (daily/research/discover) 중에 본 절차로 진입하더라도, 직전 작업의 결과를 economy 본문에 끌어오지 않는다. 깨끗한 상태로 10 섹션을 처음부터 작성 (Frontmatter + 8 본문 + Daily Facts — v4 시나리오 트리/사이클 단계 포함)한다. **섹션 압축·생략 금지** — `economy_base` 는 1일 동안 daily/research/discover 가 참조하는 정식 문서다 (LLM 의 '효율 추구' 본능을 의식적으로 차단할 것).
