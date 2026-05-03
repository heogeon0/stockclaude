# {종목명} 데일리 분석 — YYYY-MM-DD

> 템플릿. `reports/stocks/{종목}/{YYYY-MM-DD}.md` 생성 시 복사 후 채움.
> **모든 카테고리 결과를 빠짐없이 명시. "값 없음"이면 그 이유까지 적기 (DB 미적재 / 미가동 / 데이터 부족 등).**
> ⚠️ "📐 Top-down 연결" 섹션 누락 시 반쪽 daily 처리 (per-stock-analysis 출력 의무).

---

## 📐 Top-down 연결 ⭐ 필수 (v5)

> 경제 → 산업 → 종목 의 정합성을 LLM 본문 판단으로 명시. analyze_position 응답에 cell/scoring 자동 derive 가 없으므로 LLM 이 직접 인용.

**한 줄**: 경제 [{cycle_phase: 확장/정점/수축/저점}] → 산업 [{cycle_phase: 도입/성장/성숙/쇠퇴}] → 종목 상태 [{강세/관망/약세}]

**1~2줄 코멘트**: 상위 base 의 결론을 종목 판단에 어떻게 인용했는지 명시.
- 예: "경제 정점 + 산업 성숙 → 종목 멀티플 압축 리스크. signals.summary 매수우세이지만 사이즈 축소 (-10%)"
- 예: "경제 확장 + 반도체 성장 + 외인 z+2 — 강한 정합. 단 실적 D-6 이라 손절 -5% 타이트화"

**출처 인용 (각 1줄)**:
- economy_base ({market}, cycle_phase=..., scenario_probs=...): "한 줄 핵심"
- industry_base ({industry_code}, cycle_phase=..., RS_3M=±N.N%): "한 줄 핵심"
- stock_base / signals.summary 종합: "한 줄 핵심"

---

## 0. 전날 시나리오 검증 (전날 daily 있을 때만)
※ 참조 허용: 한 줄 결론 / 예측 트리거 / 손절선
※ 참조 금지: 기술분석 해석 / 투자의견 본문
- 예측 트리거: [어제 예측 조건]
- 실제 결과: ✅ / ❌ / ⏸️
- 액션 실행: 실행 / 미실행 (사유)
- 손절선 변경: 있음 / 없음
- 학습 포인트: [맞은 부분 / 틀린 부분]

## 1. 가격·거래량 (장 상태 필수)
> `realtime_price` / `kis_current_price` / `kis_us_quote` 결과
- 장 상태: 장중 / 장마감 / 시간외 / 미장 미개장
- 현재가 / 시가 / 고가 / 저가
- 등락률 (전일 종가 대비)
- 거래량 / 거래대금 (20일 평균 대비 N.Nx)
- 52주 고가 / 저가 + 이격률

## 2. 보유 현황 (position.md 있을 때)
- 보유 수량 / 평단 / 매입원가
- 평가액 / 평가손익 (₩ + %)
- 손절선까지 거리 (% / ₩)
- 비중 (KR / US / 통합)
- 변동성×재무 등급 셀

---

# 🔧 기술 분석 (5카테고리 — 모든 값 명시)

## 3. indicators — `compute_indicators` 12지표 풀 출력 ⭐ 필수
| 지표 | 값 | 해석 |
|---|---:|---|
| 종가 | ₩X | 장 상태 (장중/장마감) |
| RSI14 | NN.NN | 30↓ 과매도 / 70↑ 과열 / 80↑ 극과열 / 90↑ 폭주 |
| MACD | N | — |
| MACD 시그널 | N | — |
| MACD 히스토 | +/-N | 양수=강세 / 음수=약세 |
| ATR14 | ₩N | 1ATR 기준 손절폭 |
| Stoch_K | NN.NN | 80↑ 과열 |
| Stoch_D | NN.NN | — |
| ADX14 | NN.NN | 25↑ 추세 / 40↑ 강추세 / 60↑ 폭주 |
| SMA5/20/60/120/200 | ₩N/N/N/N/N | 정배열 / 역배열 / 부분 |
| 일목 전환선 / 기준선 | ₩N / ₩N | 호전 / 악화 |
| 볼린저 상/중/하 | ₩N/N/N | 상단 부근 / 중심 / 하단 |

→ 핵심 한 줄: "RSI X·ADX Y·MACD Z 기반 [강세/약세] [추세/횡보]"

## 4. signals — `compute_signals` 12전략 풀 출력 ⭐ 필수
| 전략 | 시그널 | 조건 | 진입가 | 손절가 |
|---|---|---|---:|---:|
| 일목균형표 | 매수/매도/관망 | (조건문 그대로) | ₩X | ₩Y |
| 래리윌리엄스 | … | … | … | … |
| 미너비니 SEPA | … | (VCP 수축 진행 명시) | … | … |
| 리버모어 피봇 | … | … | … | … |
| TripleScreen | … | … | … | … |
| 볼린저 | … | … | … | … |
| 그랜빌 SMA20 | … | … | … | … |
| 그랜빌 SMA60 | … | … | … | … |
| 그랜빌 SMA120 | … | … | … | … |
| RSI 과열 | … | … | … | … |
| 평균회귀 | … | … | … | … |
| 추세반전 | … | … | … | … |

**종합**: 강한매수 / 매수우세 / 중립 / 매도우세 / 강한매도 (매수 N / 매도 N / 관망 N, 가중합 X / Y)

## 5. volatility — `analyze_volatility`
- realized_vol (100일): NN.N%
- parkinson_vol: NN.N%
- regime: **low / normal / high / extreme** (포트 평균 대비 비교)
- max_drawdown: -NN.N% (peak NN일 전)
- current_drawdown: -NN.N%

## 6. events — `detect_events` 자동 감지
- price_break: { 52w_high_breakout / 52w_low_breakout / 없음 }
  - close_ratio_to_high: NN.N%
  - 돌파 발생 시 가격: ₩N
- rating_changes (최근 7일 analyst_reports): N건 (있으면 상세)
- 실적 D-N: 다음 발표일 / D-숫자 (D-7 이내 시 ⚠️ 강조)

## 7. chart_analysis — `compute_signals` 내 패턴 인식
- VCP 수축 단계: [N1%, N2%] (감소/증가 추세, 거래량 패턴)
- SEPA 4조건: 이평정렬 / 200MA 상승 / 52w고가 75% / 52w저가 125% (각 ✅/❌)
- 골든크로스 / 데드크로스 / 이중바닥 / 헤드앤숄더 등 감지 시 명시

---

# 📈 재무·컨센 분석 (3카테고리)

## 8. financials — `compute_financials` ⭐ 필수
> 경고가 1건이라도 있으면 ⚠️ 표기 + 비중·등급 재검토 트리거

| 항목 | 값 | 비고 |
|---|---:|---|
| 영업이익률 | N.N% | 업종 평균 대비 |
| 순이익률 | N.N% | — |
| ROE | N.N% | — |
| ROA | N.N% | — |
| 부채비율 | N.N% | 100% 미만 양호 / 200% 위험 |
| 유동비율 | N.N% | — |
| 자기자본비율 | N.N% | — |
| 이자보상배율 | N.N | 1↓ 위험 / 3↑ 양호 |
| 매출 YoY | +N.N% | — |
| 영업이익 YoY | +N.N% | — |
| 순이익 YoY | +N.N% | — |
| FCF YoY | +N.N% | — |

**경고**: ⚠️ [경고 메시지 그대로 인용] 또는 ✅ 0건
**health_summary**: A/B/C/D급 · score N/100

## 9. consensus — `get_analyst_consensus` + `analyze_consensus_trend` + `list_analyst_reports`
- 리포트 수: 최근 90일 N건
- Buy / Hold / Sell: N / N / N
- 평균 목표가: ₩N (현재가 대비 +/-N.N%)
- 최고 / 최저: ₩N / ₩N
- 표준편차 (분포 폭): ₩N
- 1M 모멘텀 (최근 30일 평균 vs 이전 30일): +/-N.N%
- rating_wave: upgrades N / downgrades N / initiations N (sentiment: positive/neutral/negative)
- 최근 7일 신규 리포트: [증권사 + TP + 코멘트]
- ⚠️ DB 비어있음 시: "스크래퍼 미가동, base.md 수치 인용"

## 10. valuation — base.md DCF / Comps / Reverse DCF 인용
- 확률가중 적정가: ₩N (현재가 대비 +/-N%)
- Bull / Base / Bear 가격대 + 확률
- Reverse DCF: 현 시총 정당화 조건 (CAGR / 영업이익률 등)
- Comps PER / PBR vs 피어
- 핵심 변수 상태

---

# 💼 포트 분석 (4카테고리 — 종목 daily에서 해당 종목 관점)

## 11. flow — `analyze_flow` 20일 (KR 전용)
| 주체 | net_total | trend | latest | z-score | 이상거래 |
|---|---:|---|---:|---:|---|
| 기관 | +/-N주 | accumulating/distributing | +/-N | +/-N.N | (날짜 z+/-N.N 이벤트) |
| 외국인 | +/-N주 | … | … | … | … |

→ 한 줄: "기관 [매집/분산] vs 외인 [매집/분산] — [충돌/쌍끌이]"

## 12. concentration — `check_concentration` (매수/피라미딩 시)
- 신규 진입 후 비중: N.N% (한도 25% 이내 / 초과)
- 시장 총액 대비 검증
- violations: [] 또는 [{detail}]
- ⚠️ 25% 초과 시: 사용자 확정 없으면 자동 집행 금지

## 13. correlation — `portfolio_correlation` (포트 전체)
> daily에서는 "이 종목과 다른 보유종목과의 상관" 발췌
- 최고 상관 페어: {종목 A} ↔ {종목 B} corr N.NNN
- 본 종목과 가장 높은 상관: {다른 종목} corr N.NNN
- effective_holdings: N.NN 종목

## 14. scoring — `compute_score` 5차원
| 차원 | 점수 | 비고 |
|---|---:|---|
| financial | N | DART 기반 |
| technical | N | daily verdict 환산 |
| valuation | N | analyst_target / 현재가 |
| industry | N | industries/{산업}/base.md meta |
| economy | N | economy_base meta |
| **total** | **N** | — |

→ 등급: **Premium (80+) / Standard (60+) / Cautious (40+) / Defensive (<40)**
→ action_template: 손절폭 / 피라미딩 / 홀딩 / 익절 / 메모

---

# 🌐 거시·산업 (2카테고리)

## 15. industry — `get_industry({산업})`
- 섹터 사이클: 슈퍼사이클 / 회복 / 성숙 / 쇠퇴
- 성장률: +N% YoY
- 경쟁 구도 / 규제 환경 / 수요 모멘텀 / 경기민감도
- 산업 score: N
- 본 종목 포지션: [업종 내 순위·차별점]

## 16. economy — `get_economy_base({market})` 인용
- 시장 국면 (regime): KOSPI/SPY 4조건 결과
- 금리 / 환율 / 외인수급 / 지정학 / 유동성 / VI
- 본 종목 거시 노출: [금리 인상 시 -X% / USD 강세 시 +Y% / 유가 +1% 시 ±Z%]

---

## 📰 뉴스 / 촉매 (WebSearch — v7 자율 호출)
- [날짜 / 헤드라인 / 출처] — `analyze_position.disclosures` / `insider_trades` 가 정형으로 커버 안 되는 nuance 발견 시만 자율 호출
- 단위별 권장 강도 → `references/websearch-rules.md` (종목/economy/industry/stock 단위별 표)
- 자율 search 미수행 시: "정형 데이터로 충분 — 자율 search 미수행" 명시

## 🎯 Watch Levels 자동 — `propose_watch_levels(entry, atr, tier)`
- 1차 목표 / 2차 / 3차 (가격 + 현재가 대비 %)
- 경고선 / 기준선 / 손절선
- 피라미딩 조건 (돌파가 + 거래량 기준)
- ATR 기반 동적 갱신 (매일)

---

## 🎯 투자의견 — 3관점 종합 판단

### 중장기 판단 (base.md 기반)
- Narrative 유효성: 유지 / 변경 / 의심 + 사유
- 확률가중 적정가 vs 현재가 → 업사이드 +/-%
- 핵심 변수 현재 상태
- base 갱신 트리거 (실적 ±10% / 컨센 ±15% / 대형 공시) 충족 여부

### 단기 기술 판단 (signals + indicators 기반)
- 12개 전략 종합 + 실질 추세 (RSI·ADX·MACD 종합)
- 주요 레벨 (저항 / 지지 / 손절)
- 변동성 regime + drawdown 상태

### 포지션별 권장 행동 (변동성×재무 매트릭스 — `stock/references/scoring-weights.md`)
- 현재 수익률 + 손익분기 거리
- **집행 전 `check_concentration()` 결과 인용**
- `propose_watch_levels` 결과로 피라미딩 / 손절 / 익절 **주 단위 구체 가격**
- 시나리오별 (돌파 / 되돌림 / 이탈) 액션 플랜

### 한 줄 결론
"{보유상태}. {가격대}에서 {행동}. {트리거} 확인 후 {조치}."

---

## 📌 Base 영향도 판단 (3-tier)

> 분류 룰: → `references/base-impact-classification.md` 참조

```
- [high/{타입}] 사실 — source: 툴/뉴스
- [medium/{타입}] 사실
- [review_needed/{타입}] 사실
- [low/daily_only] 사실
```

→ 종목 base 즉시 patch (절차: `references/base-patch-protocol.md`)

## 📌 Industry Base 영향도 (해당 시)
```
- [{산업}, high] 사실
- [{산업}, review_needed] 사실
```

## 📌 Economy Base 영향도 (해당 시)
```
- [거시, high/{타입}] 사실
```

---

## 중장기 변화 감지 → base.md 갱신 필요 여부
- 없음 / 있음: 사유 + `"/base-stock {종목} --refresh"` 힌트

## 📋 신뢰도 체크리스트 (16카테고리 커버리지)

| # | 카테고리 | 호출 | 상태 |
|---|---|---|---|
| 1 | indicators | compute_indicators | ✅ / ⚠️ {사유} |
| 2 | signals | compute_signals | ✅ / ⚠️ |
| 3 | financials | compute_financials | ✅ / ⚠️ |
| 4 | momentum | rank_momentum | (포트 daily에서만 / 종목 daily 생략 가능) |
| 5 | regime | detect_market_regime | (포트 daily에서) |
| 6 | concentration | check_concentration | (매수 시만) |
| 7 | scoring | compute_score | ✅ |
| 8 | backtest | weekly_context | (포트 daily에서) |
| 9 | flow | analyze_flow | ✅ (KR 전용) |
| 10 | events | detect_events | ✅ |
| 11 | correlation | portfolio_correlation | (포트 daily에서) |
| 12 | volatility | analyze_volatility | ✅ |
| 13 | sensitivity | (직접 툴 없음) | base 거시 노출 추정 |
| 14 | consensus | get_analyst_consensus + trend + reports | ✅ / ⚠️ DB 비어있음 |
| 15 | valuation | base.md 인용 | ✅ |
| 16 | chart_analysis | compute_signals 내 VCP/SEPA | ✅ |

- 실제 데이터 비율 / 추정·가정 비율
- 불확실 Top 3
- compute_signals 정상 여부 (버그 시 수동 판정 표기)
- ⚠️ "값 없음" 항목은 반드시 사유 적기 (DB 미적재 / 스크래퍼 미가동 / 데이터 부족)

---

## 📊 결론 메타 (v7 신설, 정량 결론) ⭐ 필수

> 추론은 자연어 (위 본문), 결론은 정량 (본 섹션). save_daily_report 호출 시 인자로 전달.
> G6 결정: 추적/검증 가능한 학습 누적의 본체.

| 필드 | 값 | 비고 |
|---|---|---|
| **verdict** | 강한매수/매수우세/중립/매도우세/강한매도 | 5종 enum, 필수 |
| **size_pct** | NN | LLM 결정 진입 사이즈 (%, 신규/유지면 0 또는 NULL) |
| **stop_method** | "%" or "ATR" | 손절 방식 |
| **stop_value** | -7 or 1.5 | % 또는 ATR 배수 |
| **override_dimensions** | `["earnings_d7", "consensus_upward", "외인_z+2"]` | 활성화 차원 list |
| **key_factors** | `[{factor: "산업 RS +18.5%", weight: "+"}, ...]` | 결정 영향 큰 요소 3~5개 |
| **referenced_rules** | `[2, 5]` | rule_catalog 인용 ID list |

→ 위 필드를 `save_daily_report(code, date, verdict, content, size_pct=..., stop_method=..., stop_value=..., override_dimensions=[...], key_factors=[...], referenced_rules=[...])` 호출 시 명시.

⚠️ 결론 메타 누락 시 weekly_review 의 정량 통계 (rule_win_rates / pattern_findings) 가 부정확해짐.
