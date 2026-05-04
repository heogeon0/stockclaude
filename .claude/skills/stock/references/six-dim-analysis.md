# 6차원 정량 분석 룰 (research 핵심)

> 로드 시점: stock-research 호출 시 매번 (모든 6차원 분석 직전).

stock-research = **공통 심도 분석 모듈**. daily / discover 가 호출.
**6차원** 각각의 해석 룰 + MCP 툴 매핑 + 출력 포맷.

---

## 1. 재무 차원

### MCP 툴
- `compute_financials(code, years=3)` — DART/SEC 3년 추이 + 비율 + 경고

### 해석 룰
| 점수 | 등급 | 의미 |
|---|---|---|
| 80-100 | **A** | 흑자 우량, ROE 15%+, 부채 적정, 경고 0 |
| 60-79 | **B** | 흑자 보통, ROE 5-15%, 부채 양호 |
| 40-59 | **C** | 소폭 흑자 / 적자 진입기, 이익질 의심 |
| <40 | **D** | 적자 지속, 부채 과다, 경고 다수 |

### 출력 포맷
- 매출/영업이익/순이익 3년 추이
- 영업이익률 / ROE / 부채비율 / 이자보상배율
- **이익의 질** = 영업CF / 순이익 비율 (1.0+ 정상, <0.5 의심)
- 경고 플래그 (compute_financials 자동 감지)

---

## 2. 기술 차원

### MCP 툴
- `compute_indicators(code, days=400)` — 12 지표 + 장 상태
- `compute_signals(code)` — 12 전략 시그널

### 해석 룰
| 종합 verdict | 매수/매도 가중 |
|---|---|
| 강한매수 | 매수 ≥ 3.5, 매도 0 |
| 매수우세 | 매수 > 매도, 매도 ≤ 1.5 |
| 중립 | 매수 ≈ 매도 |
| 매도우세 | 매도 > 매수 |
| 강한매도 | 매도 ≥ 3.5, 매수 ≤ 1 |

12 시그널 정의: → `~/.claude/skills/stock/references/signals-12.md` 참조.

### 출력 포맷
- 종합 verdict + 매수/매도/관망 카운트
- 각 시그널 진입가 / 손절가 (가능한 경우)
- RSI / Stoch / ADX / 일목 / MACD 핵심 수치

---

## 3. 수급 차원 (KR 위주)

### MCP 툴
- `analyze_flow(code, window=10)` — 기관/외인 10일 누적 + z-score 이상거래

### 해석 룰
| 신호 | 의미 |
|---|---|
| `accumulating` + z+1.0~+2.0 | 매집 진행 |
| `accumulating` + z+2.0+ | 강매집 (이상거래) |
| `distributing` + z-1.0~-2.0 | 분산 진행 |
| `distributing` + z-2.0- | 강분산 (이상거래) |
| 기관 vs 외인 엇갈림 | 방향성 불명확 |

### US 특이사항
- 일별 기관/외인 개념 없음 → **13F 분기 + 옵션 P/C ratio + Insider 매매** 3종 조합
- → `references/market-routing.md` 의 US 어댑터 참조

### 출력 포맷
- 기관 z-score / 외인 z-score
- abnormal_days (z±2 이상거래 발생일)
- 누적 추세 + 최근 5일 추이

---

## 4. 모멘텀 차원

### MCP 툴
- `rank_momentum(codes, market, lookback_days=252)` — 종목군 상대 랭킹
- `rank_momentum_wide(market, top_n, min_market_cap_krw)` — 시총 상위 광역 랭킹

### 해석 룰
| 점수 | 등급 | 의미 |
|---|---|---|
| 80+ | **A+** | Top 10% — 모멘텀 강함 |
| 65-79 | **A** | 견조 — 유지/진입 가능 |
| 50-64 | **B** | 중립 — 추가 확인 |
| 35-49 | **C** | 약함 — 매수 대기 |
| <35 | **D** | 부재 — 회피 |

상세 6차원 스코어 룰: → `references/momentum-6dim-scoring.md` 참조.
모멘텀 원칙: → `references/momentum-principles.md` 참조.
진입/청산/Crash 방어 필터: → `references/momentum-filters.md` 참조.

---

## 5. 이벤트 차원

### MCP 툴
- `detect_events(code)` — 실적 D-N + 52주 돌파 + rating change
- (옵션) `detect_earnings_surprise_tool(code, actual, consensus)` — 실적 발표 D-0±1 시

### 해석 룰
| 이벤트 | 영향도 | 처리 |
|---|---|---|
| 실적 D-7 이내 | High | 신규 진입 보류, 보유 부분 익절 |
| 52주 신고가 돌파 | Medium-High | 모멘텀 강화 + 기술 매수 |
| 52주 신저가 이탈 | Medium-High | 모멘텀 소멸 + 기술 매도 |
| Rating change (upgrade) | Medium | 컨센 모멘텀 보완 |
| Rating change (downgrade) | High | 즉시 검토 |

---

## 6. 컨센 차원

### MCP 툴
- `get_analyst_consensus(code)` — 평균 / 최고 / 최저 / 모멘텀
- `list_analyst_reports(code, days=7~90)` — 최근 리포트 목록
- `analyze_consensus_trend(code, days=90)` — 1M vs 이전 1M

### 해석 룰
| 신호 | 의미 |
|---|---|
| 평균 TP 1M 상향 +5% | 컨센 강화 |
| 평균 TP 1M 하향 -5% | 컨센 약화 |
| 신규 리포트 ≥3건 (1주일) | 커버리지 강화 |
| 만장일치 Buy (Hold+Sell <10%) | 강한 매수 컨센 |
| 표준편차 > 평균 ±20% | 의견 분포 폭 큼 (신뢰도 낮음) |

상세 룰: → `~/.claude/skills/stock/references/analyst-consensus-tracking.md` 참조 (정의처 — DRY).

---

## 종합 verdict 산정

6차원 모두 분석 후:

```
재무 등급: A/B/C/D
기술 verdict: 강한매수 / 매수우세 / 중립 / 매도우세 / 강한매도
수급 신호: 매집 / 분산 / 엇갈림
모멘텀 등급: A+ / A / B / C / D
이벤트 플래그: 실적 D-N / 52w / rating
컨센 신호: 강화 / 약화 / 만장일치 Buy / 분포 폭
```

→ 종합 판단 (논리)
→ daily / discover 가 이 결과를 받아 **액션 플랜** 또는 **진입 가능성 판단** 으로 사용

---

## 유의미 발견 → 종목 base patch (즉시)

분석 결과 중 high/medium/review_needed 분류된 fact 는 즉시 종목 base 에 append:

- 분류 룰: → `~/.claude/skills/stock/references/stock-base-classification.md` 참조
- Patch 절차: → `~/.claude/skills/stock/references/base-patch-protocol.md` 의 "종목 base patch" 섹션 참조
