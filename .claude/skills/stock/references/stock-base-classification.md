# 종목 Base 영향도 분류 룰

> 로드 시점: Daily Appended Facts 통합 시 + 갱신 트리거 판정 시.

종목 base 갱신 트리거 판정 / Daily fact 분류 / Narrative 검토 플래그 기준.

## 4단계 분류

| 분류 | 영향도 | 처리 |
|---|---|---|
| **high (fact)** | 즉시 base patch + 본문 반영 | 종목 base append + 갱신 트리거 |
| **medium (fact)** | 즉시 base patch | 종목 base append (정기 30일 갱신 시 본문 통합) |
| **review_needed (flag)** | Narrative 검토 필요 | 종목 base append + 누적 3개+ 시 base 재작성 권장 |
| **low (daily only)** | base 영향 없음 | daily 보고서에만 기록 |

## 분류 표 (사실 종류별)

| 감지 사항 | 분류 |
|---|---|
| 분기 실적 서프라이즈 ±5%+ | **high** |
| 분기 실적 서프라이즈 ±10%+ | **high (트리거)** — 즉시 갱신 모드 |
| 대형 공시 (수주·M&A·CEO 등) | **high** |
| 애널 컨센 ±10%+ 변동 (단발) | **high** |
| 애널 컨센 ±15%+ 변동 (3사 이상) | **high (트리거)** — 즉시 갱신 모드 |
| 신규 애널 리포트 ≥3건 (1주일 내) | **high (트리거)** — 즉시 갱신 모드 |
| 52주 레벨 돌파/이탈 | **medium** |
| 수급 z-score ±2+ 이상거래 | **medium** |
| Sell-the-News / 갭반전 | **review_needed** + 최상단 "🟡 base 재검토 권장" |
| 산업 구조 변화 뉴스 | **review_needed** + 산업 base append |
| Narrative 핵심 변수 상태 변화 | **review_needed (트리거)** — 즉시 갱신 모드 |
| 대주주 대량변동 (10%+) | **high (트리거)** |
| RSI/MACD/일목 과열·냉각 | **low** (base 영향 없음) |

## Append 포맷

```markdown
## 📝 Daily Appended Facts (since last full review)

### 2026-04-22
- [high/earnings] 1Q26 매출 37.6조 (컨센 35조, +7.4%) — source: DART
- [medium/flow] 외인 z+1.74 순매수 반전 — source: analyze_flow

### 2026-04-24
- [review_needed/event] Sell-the-News 우려 — narrative 검토 필요
- [high/disclosure] 미국 7,870억 변압기 수주 — source: DART
```

## 갱신 트리거 (자동 호출)

다음 조건 중 하나 충족 시 base-stock 즉시 호출 (만기 30일 무관):

1. 분기 실적 ±10% 서프라이즈
2. 컨센 평균 ±15% 조정 (3사 이상)
3. 신규 리포트 ≥3건
4. 대주주 ±10% 지분 변화
5. M&A / 분사 / 구조조정
6. Narrative 핵심 변수 상태 변화
7. **review_needed 플래그 3개+ 누적** (`Daily Appended Facts` 섹션에서 자동 카운트)
8. 만기 30일+ 경과 (정기)

## 통합 룰 (재작성 모드 시)

기존 base 의 `Daily Appended Facts` 섹션을:

1. 분류 별 (high/medium/review_needed) 묶기
2. **high** → 본문 해당 섹션에 반영
   - 컨센 변동 → 애널 컨센 섹션
   - 실적 ±5% → 재무 분석 + Forward DCF 가정 갱신
   - 대형 공시 → Narrative + 핵심 변수
3. **medium** → 핵심 변수 / 리스크 섹션
4. **review_needed** → Narrative 변경 명시 (변경 사유 기록)
5. 통합 후 `Daily Appended Facts` 비움 + last full review 날짜 갱신
