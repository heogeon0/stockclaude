# Dependency Audit (YYYY-MM-DD)

> 템플릿. `save_portfolio_summary` 직전 + `summary_content` 최상단에 삽입 필수.

```markdown
### ✅ Dependency Audit (YYYY-MM-DD)

[BLOCKING 8가지]
- [x] get_portfolio_summary(yesterday) — 매칭 N건
- [x] reconcile_actions(yesterday)
- [x] detect_market_regime — {bull/bear/sideways}
- [x] WebSearch 당일 뉴스 — {N개 이슈 확인}
- [x] economy/{오늘}.md — 생성/로드
- [x] get_stock_context — {N종} 로드 완료
- [x] WebSearch 종목별 N/N
- [x] get_weekly_context(weeks=4) — 적용 룰 강화 {요약}

[자동 재생성]
- stocks/*/base.md: {재생성 종목} / {재생성 없음}
- industries/*/base.md: {재생성 산업} / {재생성 없음}
- economy/base.md: {재생성} / {유효}
- backtest.md: {재갱신} / {유효}

[종목별 16카테고리 분석 커버리지]
| # | 카테고리 | 005930 | 036570 | NVDA | … |
|---|---|:---:|:---:|:---:|---|
| 1 | indicators | ✅ | ✅ | ⚠️ DB | … |
| 2 | signals | ✅ | ✅ | ⚠️ DB | … |
| 3 | financials | ✅ | ⚠️ 경고 | — | … |
| 4 | momentum | ✅ | ✅ | ✅ | … |
| 5 | regime | ✅ (포트 공통) |
| 6 | concentration | ✅ (매수 시만) |
| 7 | scoring | ✅ | ✅ | ✅ | … |
| 8 | backtest | ✅ (weekly_context 대체) |
| 9 | flow | ✅ | ✅ | — KR 전용 | … |
| 10 | events | ✅ | ✅ | ⚠️ DB | … |
| 11 | correlation | ✅ (포트 공통) |
| 12 | volatility | ✅ | ✅ | ⚠️ DB | … |
| 13 | sensitivity | ⚠️ 추정만 |
| 14 | consensus | ✅ / ⚠️ DB | … | … | … |
| 15 | valuation | ✅ (base.md) |
| 16 | chart_analysis | ✅ (signals 내) |

→ **요약: N6/16 카테고리 ✅ / N ⚠️**

[Base 영향도 판단 — daily content에 기록됨]
- high/medium facts: {N건 — 종목 리스트}
- review_needed: {N건 — 종목 리스트}
- 누적 3+ 경고: {종목 리스트 or 없음}

[스킵·한계 내역]
- ❌ 없음 / [항목, 사유]
- 데이터 갭 (DB 미적재 / 스크래퍼 미가동 / 산업 base 부재 등)
```

## 반쪽 daily 경고 박스

다음 중 하나라도 해당하면 `summary_content` 최상단에 박스 삽입 필수:
- `[ ]` 또는 `❌` 항목 잔존
- `analyze_position` 결과 중 `coverage_pct < 80%` 종목 1개 이상
- `coverage_warning` 필드가 None 아닌 종목 1개 이상

```markdown
> ⚠️ **반쪽 daily — 아래 항목 누락**
> - WebSearch 당일 뉴스 미수행
> - compute_financials 005930 실패
> - 086790 coverage 70% (consensus DB empty + financials 경고 처리 못함)
> - NVDA/GOOGL OHLCV DB 미적재로 indicators/signals/events 분석 불가
>
> 이 보고서는 완전한 분석이 아니며, 내일 /stock-daily 재실행 권장
```

## Phase Audit (v2 7-Phase Pipeline)

매 daily 마무리 시 Phase별 호출 검증 표 자동 출력 — 누락 시 ⚠️ 강제.

```markdown
### 🔍 Phase Audit
| Phase | 호출 툴 | 호출 수 | 상태 |
|---|---|---|---|
| 0. 신선도 + 스코프 | `list_daily_positions`, `check_base_freshness(auto_refresh=True)` | 2 | ✅ |
| 1. 과거 학습 회수 | `get_portfolio_summary(yest)`, `reconcile_actions(yest)`, **`list_trades`**, **`reconcile_actions(today)`**, `get_weekly_context` | 5 | ✅ |
| 2. 매크로·국면 | `detect_market_regime`, `WebSearch` | 2 | ✅ |
| 3. 종목 분석 | `analyze_position × N` (Active+Pending) + 종목별 WebSearch | N×2 | ✅ (avg coverage X.X%) |
| 4. 분류 (Cell+Verdict) | (Phase 3 derive) | — | ✅ |
| 5. 액션 결정 | (decision-tree.md 적용) | — | ✅ |
| 6. 게이트 | `check_concentration` (집행 시) | 0~N | — / ✅ |
| 7. 저장 | `save_daily_report × N`, `save_portfolio_summary` (옵션 `reconcile_actions(today)` 흡수) | N+1 | ✅ |

**총 호출**: M / 예상 M ✅
**평균 coverage**: X.X% (임계값 80%, 미달 시 ⚠️)
**자동 트리거**: [/base-* 자동 호출 내역 또는 "없음"]
**게이트 실패**: [집행 차단된 종목 또는 "없음"]
```

## 16카테고리 분석 툴 매핑 (종목별 daily 필수)

| # | 카테고리 | MCP 툴 | 출력 명시 항목 |
|---|---|---|---|
| 1 | **indicators** | `compute_indicators(code)` | RSI/MACD/BB/MA5/20/60/120/200/ATR/Stoch/ADX/일목 |
| 2 | **signals** | `compute_signals(code)` | 12전략 시그널 + 진입가/손절가 + 종합 |
| 3 | **financials** | `compute_financials(code)` | 영업이익률/ROE/부채/이자배율/YoY + 경고 |
| 4 | **momentum** | `rank_momentum(codes=[..])` | 6차원 모멘텀 Z-score |
| 5 | **regime** | `detect_market_regime()` | bull/bear/sideways + 4조건 |
| 6 | **concentration** | `check_concentration(code, qty, price)` | 25% 룰 violations |
| 7 | **scoring** | `compute_score(code, timeframe)` | 5차원 점수 + Premium/Standard/Cautious/Defensive |
| 8 | **backtest** | `get_weekly_context(weeks=4)` | 룰별 win-rate + carryover |
| 9 | **flow** | `analyze_flow(code, window=20)` | 기관/외인 net + z-score + 이상거래 |
| 10 | **events** | `detect_events(code)` | 52w 돌파 자동 / rating change / 실적 D-N |
| 11 | **correlation** | `portfolio_correlation(days=60)` | avg corr / effective_holdings |
| 12 | **volatility** | `analyze_volatility(code)` | realized_vol / parkinson / regime / DD |
| 13 | **sensitivity** | (직접 툴 없음) | 거시 노출 추정 (금리/환율/유가 베타) |
| 14 | **consensus** | `get_analyst_consensus + analyze_consensus_trend + list_analyst_reports` | TP / Buy/Hold/Sell / 1M momentum / rating wave |
| 15 | **valuation** | base.md DCF 인용 | 확률가중 적정가 / Bull·Base·Bear |
| 16 | **chart_analysis** | `compute_signals` 내 VCP/SEPA | VCP 수축 / SEPA 4조건 / 패턴 인식 |

## 추가 조건부 호출

- 실적 발표일 D-0 ±1 시: `detect_earnings_surprise_tool(code, actual, consensus)`
- 신규 진입 시: `propose_watch_levels(code, entry, atr, tier, persist=True)` (ATR 기반 watch_levels 갱신)
- US 종목: `kis_us_quote(ticker, exchange)` + 13F/옵션 체인/Insider 3종 (v11 US 어댑터)
- 산업 base 만료 시: `get_industry({산업})` 로드 (만기 7일)
- 경제 base 만료 시: `get_economy_base({market})` 로드 (만기 1일)

## 데이터 갭 처리 룰

- **DB OHLCV 미적재 (US 등)**: KIS API 직접 조회만 가능 → indicators/signals/events 스킵, daily에 ⚠️ 표기
- **컨센 스크래퍼 미가동**: get_analyst_consensus null → base.md 수치 인용 + ⚠️ 표기
- **산업 base 부재**: `/base-industry {산업}` 권장 메시지 + 임시 사용자 입력 가능
- 모든 갭은 daily 본문 + audit에 명시 (감춤 금지)
