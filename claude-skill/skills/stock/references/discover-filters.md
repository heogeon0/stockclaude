# 발굴 필터 룰 (1/2/3 단계)

> 로드 시점: 신규 발굴 시 후보 필터링 + 추천 결정 시.

## 1단계 — 광역 스크리닝 필터

### 후보 30~50개 확보

**유동성 + 모멘텀 교집합 우선**:

```python
# 유동성 상위 50
liquidity_top = list_tradable_stocks(
    market='kr',
    sort_by='trade_value',
    min_market_cap_krw=3_000_000_000_000,  # 시총 3조+
    limit=50,
)

# 모멘텀 상위 30
momentum_top = rank_momentum_wide(
    market='kr',
    top_n=30,
    min_market_cap_krw=3_000_000_000_000,
)

# 교집합 우선 / 합집합 차선
intersection = set(liquidity_top) & set(momentum_top)
union = set(liquidity_top) | set(momentum_top)
candidates = list(intersection) + [c for c in union if c not in intersection]
candidates = candidates[:50]
```

### 필터 원칙

- **시총 3조 미만 제외** (유동성 리스크)
- **거래대금 100억 미만 제외** (슬리피지)
- **보유 종목 제외** (or 확장 후보로 별도 메모)
- 상장폐지 / 거래정지 종목 제외

## 2단계 — 좁은 분석 필터

### Top 10~15 선별

각 후보별로 stock-research 호출 (또는 핵심 MCP 직접):

```python
for code in candidates:
    indicators = compute_indicators(code)
    signals = compute_signals(code)
    financials = compute_financials(code)
    score = compute_score(code)  # 변동성×재무 매트릭스 자동 적용
    volatility = analyze_volatility(code)
```

### 2단계 랭킹 기준 (복합)

- **`score.total_score` Top 30 우선**
- **`signals.summary.종합` ∈ ('강한매수', '매수우세')** (중립 이하 탈락)
- **`volatility.regime` ∈ {normal, high}** (extreme 은 신중)
- **재무 등급 ≥ B** (D급 적자 종목은 비추 — 변동성×재무 매트릭스 D급 비추 셀)
- **`financials.ratios.per` < 업종 평균 1.3배** (밸류 함정 회피)

→ 위 5개 중 4개 이상 충족 시 Top 10~15 선별.

## 3단계 — Deep Dive 필터

### 최종 Top 3~5

Top 10~15 각각에 대해:

```python
events = detect_events(code)
trend = analyze_consensus_trend(code)
consensus = get_analyst_consensus(code)
flow = analyze_flow(code)
concentration = check_concentration(code, qty=intended_qty, price=current_price)
```

### 3단계 필터

| 트리거 | 행동 |
|---|---|
| **실적 D-3 이내** | "대기" 표시 (당장 진입 X) |
| **애널 커버 < 3건 + 소형주** | 리서치 정확도 낮음 경고 |
| **수급 4주 연속 외인 매도** | 과열 종목이면 경계선 |
| **집중도 시뮬 > 25%** | 진입 보류 (또는 사이즈 축소) |
| **변동성×재무 셀 비추** (D급+extreme) | 즉시 탈락 |

## 변동성×재무 매트릭스 적용 (v17 새 룰)

추천 시 진입 사이즈 자동 결정:

```python
vol_regime = volatility.regime
fin_ratios = financials.ratios
fin_growth = financials.growth

# v6 (2026-05): 매트릭스 룩업 폐지 (anchor 효과 + 검증 안 된 직관적 설계).
# 산업 평균 대비 LLM 본문 판단 — industries.avg_per/avg_pbr/avg_roe/avg_op_margin 인용.
# 거장 원칙은 master-principles.md 의 10 카테고리 참조.

# 산업 평균 대비 financial_grade (A/B/C/D) 본문 판단
# - PER vs industries.avg_per → 할인/프리미엄
# - ROE vs industries.avg_roe → 우열
# - 영업이익률 vs industries.avg_op_margin → 마진 우열
# - 변동성 regime vs industries.vol_baseline_30d → regime 보정

# 진입 사이즈 / 피라미딩 / 손절폭은 LLM 본문 판단:
# - master-principles 의 손익 관리 / 변동성 관리 / 사이클 인식 카테고리 인용
# - check_concentration 게이트 통과 후 결정
```

판단 룰: → `~/.claude/skills/stock/references/master-principles.md` (10 카테고리 거장 원칙). 옛 매트릭스 룩업은 `_archive/scoring-weights.md` 보존 — 인용 X.

**단타/스윙/중장기/모멘텀 4종 폐지** (v17). `compute_score(code, '스윙')` 호출의 `'스윙'` 인자 제거 / 기본값 사용.

## 출력 템플릿

→ `assets/discover-output-template.md` 참조.

## 한 줄 결론 의무

각 최종 추천 끝에:

> "{종합 등급} — {핵심 논리 한 줄}. {셀명} 셀 적용 → 진입가 ₩X 기준 X주 ({size}), 손절 ₩Y, 1차 목표 ₩Z."

예:
> "Standard — 1Q26 분기 사상최대 + VCP 정석 + PBR 0.76 저평가. B-normal 셀 → 진입가 ₩125,200 기준 25주 (풀 진입), 손절 ₩115,300 (-7.9%), 1차 목표 ₩133,700 (+6.8%)."
