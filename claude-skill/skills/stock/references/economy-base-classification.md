# 경제 Base 영향도 분류 룰

> 로드 시점: economy/{날짜}.md 작성 시 + base 갱신 트리거 판정 시.

## 4단계 분류

| 분류 | 영향도 | 처리 |
|---|---|---|
| **high (fact)** | 즉시 base patch + 본문 반영 | economy base append + 갱신 트리거 |
| **medium (fact)** | 즉시 base patch | economy base append (1일 만기 갱신 시 본문 통합) |
| **review_needed (flag)** | 섹터 포지셔닝 재검토 | base append + 누적 3개+ 시 base 재작성 권장 |
| **low (daily only)** | base 영향 없음 | economy daily 에만 기록 |

## 분류 표

| 감지 사항 | 분류 |
|---|---|
| **FOMC 결정 (금리 인상·인하·시그널 변화)** | **high (트리거)** — 즉시 base 재작성 |
| 한은 금통위 결정 | **high (트리거)** |
| **CPI/PCE 컨센서스 ±0.2%p** 상회/하회 | **high** |
| **환율 레짐 전환** (1,400+, 1,500+, 1,300- 등 임계) | **high (트리거)** |
| **주요 지수 ±2%+ 변동** (코스피, S&P 500) | **medium** |
| 외국인 누적 순매수/매도 ±2조 (1주일 내) | **medium** |
| WTI 또는 금 ±5% (1주일 내) | **medium** |
| **섹터 전반 유턴** (반도체 / 게임 / 방산 등) | **review_needed** |
| **지정학 이벤트** (제재 / 무역 / 전쟁 / 휴전) | **review_needed (트리거)** |
| 정치 / 선거 결과 | **review_needed** |
| 일일 코스피 등락률 ±1% 미만 | **low** (base 영향 없음) |

## Append 포맷

```markdown
## 📝 Daily Appended Facts (since last full review)

### 2026-04-23
- [high/rates] 연준 6월 인하 전망 약화 (CPI 3.1% 예상 상회) — source: WebSearch
- [medium/fx] 원/달러 1,420원 돌파 — 수출주 수혜 narrative 강화

### 2026-04-24
- [review_needed/geopolitics] 중국 반도체 규제 확대 검토 — 'US-China tension' 재평가
```

## 갱신 트리거 (자동 호출)

다음 조건 중 하나 충족 시 base-economy 즉시 호출 (만기 1일 무관):

1. FOMC / 한은 금통위 결정
2. CPI / PCE ±0.2%p
3. 환율 레짐 임계 돌파
4. 지정학 대형 이벤트 (전쟁 / 휴전 / 제재 발효)
5. **review_needed 플래그 3개+ 누적**

## 통합 룰 (재작성 모드)

기존 `Daily Appended Facts` 섹션을:

1. 분류 별 묶기
2. **high** → 본문 해당 섹션
   - 금리 정책 변화 → "금리/유동성" 섹션
   - CPI 변화 → "금리/유동성" + "경기/지수"
   - 환율 레짐 → "환율/무역"
3. **medium** → 추세 / 누적 변화 반영
4. **review_needed** → "섹터 포지셔닝" 재검토 명시
5. 통합 후 섹션 비움 + last full review 날짜 갱신

## stock-daily 와 공유

이 룰은 stock-daily 의 economy daily 작성 시에도 동일 적용:
- → `~/.claude/skills/stock/references/base-impact-classification.md` 의 "경제 base 영향도 분류" 표와 cross-link
- DRY 원칙: 본 파일이 정의처, stock-daily 는 참조만
