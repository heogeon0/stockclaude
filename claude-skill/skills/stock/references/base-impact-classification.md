# Base 영향도 분류 룰

> 로드 시점: 데이터 수집 후 daily 보고서 작성 시 (특히 `📌 Base 영향도 판단` 섹션 작성 직전).

종목 daily에서 감지한 이벤트를 4단계로 분류해 **종목 base.md / Narrative 검토 플래그 / daily 한정** 결정.

## 종목 base 영향도 분류

| 감지 사항 | 분류 | 기록 위치 |
|---|---|---|
| 분기 실적 서프라이즈 ±5%+ | **high (fact)** | daily content + 종목 base append |
| 대형 공시 (수주·M&A·CEO 등) | **high (fact)** | 동일 |
| 애널 컨센 ±10%+ 변동 | **high (fact)** | 동일 + watch levels 재계산 명시 |
| 52주 레벨 돌파/이탈 | **medium (fact)** | 동일 |
| 수급 z-score ±2+ 이상거래 | **medium (fact)** | 동일 |
| Sell-the-News / 갭반전 | **review_needed (flag)** | 동일 + 최상단 "🟡 base 재검토 권장" 경고 |
| 산업 구조 변화 뉴스 | **review_needed (flag)** | 동일 + 산업 base append (추가) |
| RSI/MACD/일목 과열·냉각 | **low (daily only)** | 이 섹션에 기록 안 함 (base 영향 없음) |

## 산업 base 영향도 분류 (종목 daily 부가 섹션)

종목 daily 분석 중 **산업 전반 이슈** 감지 시 별도 기록 (종목 base와 분리):

| 감지 사항 | 예시 | 분류 |
|---|---|---|
| 산업 경쟁 구도 변화 | "HBM4 시장 SK하이닉스 주도권 확대" | high (fact) |
| 규제·정책 변화 | "게임 셧다운제 완화" | high (fact) |
| 기술 패러다임 | "AI 반도체 수요 재평가" | medium (fact) |
| 섹터 전반 수급 전환 | "외국인 반도체 순매수 10일 연속" | medium (fact) |
| 산업 이벤트 (인수·M&A) | "경쟁사 적대적 M&A 시도" | review_needed |

## 경제 base 영향도 분류 (economy/{오늘}.md 작성 시)

경제 daily 관찰 → economy/base.md 갱신 필요 시 자동 분류:

| 감지 사항 | 분류 | 기록 |
|---|---|---|
| 금리 정책 변화 (인상·인하·시그널) | high (fact) | economy daily에 구조화 기록 |
| 환율 레짐 전환 (1,400+, 1,500+ 등) | high (fact) | 동일 |
| CPI/PCE 컨센서스 상회·하회 ±0.2%p | medium (fact) | 동일 |
| 주요 지수 ±2%+ 변동 | medium (fact) | 동일 |
| 섹터 전반 유턴 (반도체 급락/급등) | review_needed | 동일 |
| 지정학 이슈 (제재·무역·전쟁) | review_needed | 동일 |

## 출력 포맷 (daily 보고서 안에 넣을 섹션)

### 종목 base 영향도

```markdown
## 📌 Base 영향도 판단
- [high/earnings] 1Q26 매출 37.6조 (컨센 35조, +7.4%) — source: DART
- [medium/flow] 외인 z+1.74 순매수 반전 — source: analyze_flow
- [review_needed/event] Sell-the-News 우려 — narrative 검토 필요
```

### 산업 base 영향도 (종목 daily 부가)

```markdown
## 📌 Industry Base 영향도 판단
- [반도체, high] HBM4 수주 경쟁 — 하이닉스·삼전 공통 이슈
- [게임, review_needed] 신작 실패 사례 다수
```

### 경제 base 영향도 (economy/{오늘}.md 안)

```markdown
## 📌 Economy Base 영향도 판단
- [high/rates] 연준 6월 인하 전망 약화 (CPI 3.1% 예상 상회) — source: WebSearch
- [medium/fx] 원/달러 1,420원 돌파 — 수출주 수혜 narrative 강화
- [review_needed/geopolitics] 중국 반도체 규제 확대 검토 — 'US-China tension' 재평가
```

## 누적 경고 룰

- review_needed 플래그 **3개+ 누적** 시 daily 최상단 "🟡 base 재검토 권장 — `/base-stock` 권장" 경고 박스 필수
- 축적 기간이 60일+ (research 오래됨) 이면 자동 재생성 트리거 (`expiration-rules.md`와 연동)

## Patch 절차

base patch 절차는 → `references/base-patch-protocol.md` 참조 (3-tier별 호출 시퀀스 정의).
