# Discover Workflow — 신규 종목 발굴 절차

> stock skill 의 discover 모드 진입 시 따라야 할 워크플로우.
> 광역 모멘텀 → 좁은 분석 → 변동성×재무 매트릭스 → Top 3~5.

---

## 원칙

**모멘텀·유동성 먼저, 그 다음 6차원 분석 + 변동성×재무 매트릭스**.

이유:
- 모멘텀·유동성 = 시장이 주목하는 종목 빨리 포착
- 2,500+ 종목 중 의미 있는 건 보통 50~100개
- 거기서 6차원 정량 분석 + 매트릭스 셀 룩업으로 3~5개 집중

### ⛔ 광역 모멘텀이 메인, DB 필터는 부산물

- ✅ **메인 발굴 경로**: `rank_momentum_wide(market)` → LLM 선별 → research → 통과 종목 자동 stock_base 작성 → DB 풀 자연 누적
- ⚠️ **부산물**: `screen_stocks` / `discover_by_theme` 는 **신규 발굴 도구가 아님**. 이미 분석된 종목 풀에서 재참조용. 풀이 작아 신규 발굴 효과 거의 없음.

### KR / US 시장 라우팅 (v18)

- **KR**: pykrx → KOSPI+KOSDAQ ~2,500 → 시총 5조+ → naver 일봉 → momentum_score
- **US**: S&P 500 ∪ NASDAQ 100 ~530 → 시총 $10B+ → yfinance batch → momentum_score
  - `rank_momentum_wide(market="us", min_market_cap_usd=10_000_000_000, top_n=30)`
  - 첫 호출 시 시총 fetch 시리얼 (~3분, 200 종목) — 일 1회 사용 가정
  - momentum_score 시장 무관 (KR/US 동일 6차원 점수)

---

## 3단 워크플로우

### 1단계. 광역 스크리닝 — 후보 30~50개

```python
discover_by_theme(keyword="AI 전력", market="kr")  # 테마 있으면
# 또는
list_tradable_stocks(market='kr', sort_by='trade_value', limit=50)
+ rank_momentum_wide(market='kr', top_n=30)
# → 교집합 우선, 합집합 차선
```

상세 필터 룰: → `discover-filters.md` 참조.
테마 키워드: → `theme-keywords.md` 참조.

### 2단계. 좁은 분석 — Top 10~15

각 후보별 research 모드 호출 (또는 핵심 MCP 직접):

```python
analyze = stock_research(code)  # 6차원 정량 — research-workflow.md
# 또는 직접 MCP
compute_signals(code)
compute_financials(code)
compute_score(code)
analyze_volatility(code)
```

랭킹 + 변동성×재무 셀 적용: → `discover-filters.md` 참조.

### 2.5단계. 시그널 백테스트 (Top 5~7 후보)

선별 좁힌 후 각 후보의 12 시그널 신뢰도를 종목별로 측정:

```python
# 1순위: base 에 백테스트 섹션 있으면 거기서 읽기 (재호출 절감)
ctx = get_stock_context(code)
if ctx.get("base") and "9. 📉 시그널 백테스트" in ctx["base"].get("content", ""):
    # base 의 9번 섹션 파싱해서 사용
    pass
else:
    # base 없거나 백테스트 섹션 없으면 실시간 호출
    backtest_signals(code, lookback=200)
```

→ base 만기 (30일) 동안은 **재계산 X** — 신규 발굴 종목만 실시간.

활용 룰 (Phase 1 — 정보 첨부, 자동 가중치 X):
- 시그널당 발생 횟수 **≥ 10회** 인 것만 신뢰 (표본 부족 ⚠️ 표시)
- 20일 hold 승률 **≥ 60%** + 평균수익 **+2%** 이상 = ⭐⭐⭐ (강신뢰)
- 승률 50~60% = ⭐⭐ (참고)
- 승률 < 50% = ⭐ (역지표 가능성, 명시 회피 권장)

LLM 이 종목 추천 시 신뢰도 별 시그널 활용. 자동 가중치 조정 X (과적합·표본 부족 위험 — Phase 2 검증 후 도입).

### 2.6단계. Pending 등록 시 base 작성 → 백테스트 영구 기록

사용자가 추천 종목 "관심 등록" 요청 시:
1. `register_stock(code, ...)` — stocks 등록 (industry_code 매핑 의무)
2. `Agent("base-stock-updater", code=...)` spawn — 9 섹션 + **9번 백테스트 섹션 자동 작성**
3. `propose_watch_levels(persist=True)` — 감시 레벨

이후 30일 만기 시 base-stock-updater 가 백테스트 자동 갱신. discover 시 같은 종목 재발굴되면 base 에서 읽기 (속도↑).

### 3단계. Deep Dive — Top 3~5

```python
detect_events(code)              # 실적 임박? 52주 돌파?
analyze_consensus_trend(code)    # 컨센 모멘텀
analyze_flow(code)               # 수급 매집/분산
check_concentration(code, qty)   # 비중 시뮬
```

3단계 필터 (실적 D-3 / 애널 커버 / 수급 / 집중도): → `discover-filters.md` 참조.

---

## 출력 포맷

→ `~/.claude/skills/stock/assets/discover-output-template.md` 참조 (Top 3~5 추천 + 1단계/2단계/비추 종목 구조).

---

## 4단계 (선택) — Pending 등록

사용자가 "관심 등록" 요청 시:
- MCP multi-step orchestration (LLM 직접) 의 `register_as_pending()` 호출
1. stocks 테이블 등록 (필요 시)
2. **base-stock-updater sub-agent spawn** → 풀 base.md 작성
3. positions 에 Pending row (qty=0)
4. watch_levels 자동 등록 (`propose_watch_levels(persist=True)`)

이후 daily 가 Pending 종목도 자동 추적 (트리거 가격 도달 시 alert).

---

## 변동성×재무 매트릭스 적용

추천 시 진입 사이즈 / 피라미딩 / 손절 자동 결정:

- 변동성: `analyze_volatility(code).regime` → normal / high / extreme
- 재무: `compute_score(code).breakdown.financial` → A / B / C / D
- 셀별: 진입 사이즈 (풀/70%/50%/30%/비추) / 피라미딩 단계 / 손절폭

→ 12셀 매트릭스: `~/.claude/skills/stock/references/scoring-weights.md` 참조.

**D급 + extreme 셀 = 비추** — 자동 탈락.

---

## 주의사항

### 할루시네이션 방어

- MCP 조회 실패 종목은 **절대 추천 금지**
- base 없는 종목: "리서치 미작성, 기술·공개재무로만 평가" 명시
- 애널 커버 없는 종목: "애널 컨센 불가" 명시

### 집중도

- 후보 종목이 이미 보유 섹터와 동일 시 `portfolio_correlation` → 중복 경고
- 최종 추천 시 항상 `check_concentration(code, qty, price)` 포함

### 유동성 함정

- 시총 3조 이상 원칙
- 거래대금 100억 미만 제외
- 개인 순매수 과다(>70%) 종목 경계

### 실적 임박

- D-7 이내 종목은 "대기" 로 표시 (진입 리스크)
- D-14~7 구간은 포지션 축소 권장

---

## 한 줄 결론 필수

각 최종 추천 끝에:

> "{종합 등급} — {핵심 논리 한 줄}. {셀명} 셀 적용 → 진입가 ₩X 기준 X주 ({size}), 손절 ₩Y, 1차 목표 ₩Z."

---

## 보조 파일 인덱스

- `discover-filters.md` — 1/2/3단계 필터 + 변동성×재무 매트릭스 적용
- `theme-keywords.md` — 테마별 키워드 매핑 (10+ 카테고리)
- MCP multi-step orchestration (LLM 직접) — Pending 등록 자동화
- `~/.claude/skills/stock/assets/discover-output-template.md` — 표준 출력
