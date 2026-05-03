# 모멘텀 투자 5대 원칙 (momentum 흡수)

> 로드 시점: 모멘텀 분석 시 (research / discover / daily 모두 참조).

이전 stock-momentum SKILL.md 에서 흡수.

## 5대 원칙

### 1. Cross-sectional 우선

- 개별 종목의 강한 모멘텀보다 **종목군 대비 상대 강도** 가 예측력 높음
- 단순 12-1 수익률보다 **Z-score 상대 랭킹** 이 신뢰도 높음
- 출처: Jegadeesh & Titman (1993), Asness et al. (2013)

### 2. 시장 국면 필터 선행

- KOSPI 가 10개월선 아래면 모멘텀 전략 **Off**
- VIX/V-KOSPI 급등 시 신규 진입 축소
- 출처: Mebane Faber (2007), Gary Antonacci (2014)

```python
detect_market_regime(reference_code='005930')  # KR
# 결과의 모멘텀_가동 필드 — False면 신규 매수 중단
```

### 3. 정기 리밸런싱

- 월 1회 또는 분기 1회 전면 교체 원칙
- 데일리 시그널 추격 ❌
- 모멘텀 = 1~12개월 시그널이지 1~7일 시그널 아님

### 4. 진입 전 심층 검증

- 모멘텀 Top 후보라도 **Narrative / DCF / 딜 레이더** 검증 필수
- "단순 가격이 빠르게 오른 이유 = 펀더멘털 호전" 인지 확인
- 단순 momentum chasing → 50%+ 실패율

### 5. Momentum Crash 방어

- V-KOSPI > 40 → 신규 진입 중단
- KOSPI Breadth < 0.3 → 신규 진입 50% 축소
- KOSPI 10M MA 이탈 → 전면 방어 전환 (현금 비중 50%+)
- 상세: → `references/momentum-filters.md` 참조

## 적용 매트릭스

| 시점 | skill | 적용 원칙 |
|---|---|---|
| 신규 발굴 | stock-discover | 1, 4 |
| 종목 분석 | stock-research | 1, 4 |
| 매일 추적 | stock-daily | 2, 5 |
| 월간 점검 | (research --rebalance) | 3, 5 |

## 모멘텀 단독 사용 금지

모멘텀은 **6차원 중 1차원** — 단독으로 진입 결정 X.
반드시 재무 + 기술 + 수급 + 이벤트 + 컨센 종합 후 결정.

→ `references/six-dim-analysis.md` 참조.

## 시장 차이 (KR vs US)

| 시장 | 유니버스 | 벤치마크 | 국면 지표 |
|---|---|---|---|
| KR | KOSPI 200 또는 시총 상위 100 | KOSPI 지수 | KOSPI 200MA + V-KOSPI |
| US | S&P 500 또는 Russell 1000 상위 100 | SPY ETF | SPY 200MA + VIX + 10Y-3M Yield |

## 스타일 폐지 (v17)

기존 stock-momentum 의 "단타 / 스윙 / 중장기" 분기는 **폐지**.

## 액션 결정 (v6, 2026-05)

옛 매트릭스 룩업 (`_archive/scoring-weights.md`) 도 v6 에서 anchor 효과 + 검증 안 된 직관적 설계로 폐기. 대체:
→ `~/.claude/skills/stock/references/master-principles.md` 의 10 카테고리 거장 원칙 (Livermore / Minervini / O'Neil / Weinstein / Buffett / Marks / PTJ / Lynch). LLM 본문 판단으로 산업 평균 대비 / Top-down 정합성 / 변동성 regime 종합.
