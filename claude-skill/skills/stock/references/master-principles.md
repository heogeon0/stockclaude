# Master Trading Principles — 거장 트레이딩 원칙

> 검증된 트레이딩 거장의 핵심 원칙. **추상 방향성만**, 구체 수치 X.
> per-stock-analysis 의 6단계 LLM 판단에서 출발점으로 인용. 케이스별 적용은 LLM 본문 판단.
>
> **anchor 효과 제거**: 룩업 매트릭스 (scoring-weights / decision-tree / position-action-rules) 는 v6 (2026-05) 에서 _archive 로 이동.
> 이 파일은 그 자리를 채우는 검증된 원칙 표준. 매트릭스가 아닌 **방향성 원칙**.

---

## 1. 손익 관리 — "Cut losses, let winners run"

**출처**: Jesse Livermore (Reminiscences of a Stock Operator), Mark Minervini (SEPA), William O'Neil (CAN SLIM), Paul Tudor Jones

핵심:
- **손실 종목에 추가 매수 X** (loser averaging — 가장 흔한 파괴적 실수)
- **익절은 추세 끝까지, 손절은 즉시** — 비대칭 손익 비율로 장기 흑자
- **단일 거래 리스크 1~2% per trade** (PTJ) — 포트 자본의 일부만 위험에 노출
- **7% 룰** (Minervini) — 7% 손실 도달 전에 무조건 손절. 회복에 14% 필요

> 케이스별 LLM 판단: 변동성 종목은 % 대신 ATR 기반 손절. 종목별 베타·유동성 따라 조정.

---

## 2. 추세 추종 — "The trend is your friend"

**출처**: Jesse Livermore, Larry Williams, Stan Weinstein, Richard Dennis (Turtles)

핵심:
- **추세에 맞서지 말 것** — 역추세 매매는 신중 (전체 거래의 20% 이내 권장)
- **신고가 돌파 + 거래량 1.5x = 모멘텀 신호** — 단 추격은 자제
- **Pyramiding**: 추세에 맞춰 추가 매수, 손실엔 추가 X (Livermore 핵심 룰)
- **추세 정의는 장기 + 중기 + 단기 정합** — 일봉/주봉 동시 상승

> 케이스별 LLM 판단: regime 약세장에선 매수 시그널이라도 사이즈 축소. 강세장에선 트레일링.

---

## 3. 변동성 관리

**출처**: Mark Minervini, Mark Douglas (Trading in the Zone), Nassim Taleb

핵심:
- **변동성 클수록 사이즈 축소** — 같은 자본 대비 노출 일정 유지
- **ATR 기반 손절** — % 손절은 일상 변동성 큰 종목 (예: 신흥 / 중소형) 에 부적합
- **평균 거래량 변화 추적** — 거래량 ↓ + 가격 ↑ = 추세 약화 의심
- **변동성 regime 전환 인식** — low → high 전환 시 사이즈 즉시 축소

> 케이스별 LLM 판단: extreme regime 종목은 신규 진입 보류. 보유 시 ATR×1.5~2 손절.

---

## 4. 사이클 인식 — Stage Analysis

**출처**: Stan Weinstein (Secrets for Profiting in Bull and Bear Markets)

핵심 4단계:
- **Stage 1 — 저점 횡보** (Basing): 횡보 누적, 거래량 미미. 진입 X (대기)
- **Stage 2 — 상승 추세** (Markup): 200MA 상승 돌파 + 거래량 폭증. **매수 영역**
- **Stage 3 — 고점 횡보** (Distribution): 모멘텀 둔화, 분산 신호. 부분 익절 / 트레일링
- **Stage 4 — 하락 추세** (Markdown): 200MA 이탈. **매도 / 진입 금지**

> Stage 전환 신호: 200MA 돌파 + 거래량 + 추세 폭(breadth) 정합. LLM 이 본문 판단으로 Stage 결정.

---

## 5. 재무 우량 + 모멘텀 — SEPA / CAN SLIM

**출처**: Mark Minervini (SEPA), William O'Neil (CAN SLIM)

핵심:
- **재무 약한 종목은 모멘텀 좋아도 신중** — 사이즈 축소 / 보유 기간 짧게
- **ROE 가속도 / EPS 성장 가속** 우선 (절대값보다 추세)
- **영업이익 YoY +25% 이상** 종목 모멘텀 가중
- **CAN SLIM**: Current earnings + Annual earnings + New product/management + Supply&demand + Leader + Institutional + Market direction
- **VCP (Volatility Contraction Pattern)**: 진입 전 변동성 수축 확인 (Minervini)

> 케이스별 LLM 판단: 재무 D + 모멘텀 신호 시 진입 보류. 산업 평균 대비 ROE 비교.

---

## 6. 이벤트 리스크

**출처**: Jesse Livermore (실적 직전 보수), Warren Buffett (event 분석 전 사이즈 축소)

핵심:
- **실적 발표 직전 (D-7 이내) 사이즈 축소** / 손절 타이트화
- **재무 가이던스 변경 시 즉시 재평가** — 시그널 다 맞아도 가이던스 부정 우선
- **M&A / 분사 / 유상증자 / 자사주 / 블록딜** = 비대칭 이벤트 → 별도 처리 (정성 판단)
- **컨센 변경 ±10% 이상 → 재평가 트리거**

> 케이스별 LLM 판단: events.earnings.D-N ≤ 7 시 손절 자동 타이트화. rating_changes 상향/하향 인용.

---

## 7. Top-down — 시장 → 산업 → 종목

**출처**: Howard Marks (memos, "The Most Important Thing"), Stanley Druckenmiller, Soros

핵심:
- **시장 regime 약세 → 모든 종목에 매도 가중치** — 좋은 종목도 피해갈 수 없음
- **산업 사이클 쇠퇴 → 종목 turnaround thesis 도 의심** — 산업 역풍 거슬러 매수 X
- **산업 RS 약세 종목**은 좋은 종목도 보류 (모멘텀 결여)
- **3층 정합성**: 경제 cycle_phase × 산업 cycle_phase × 종목 상태 모두 인용 의무

> 케이스별 LLM 판단: per-stock-analysis 6단계의 Top-down 정합성 본문 판단. daily-report 의 "📐 Top-down 연결" 섹션 인용.

---

## 8. 인내와 규율 — "Wait for fat pitches"

**출처**: Warren Buffett, Charlie Munger, Ted Williams

핵심:
- **좋은 기회만 기다림** — 강한매수 + Top-down 정합 + 게이트 통과 시점만
- **욕심·공포 제어** — 변동성 큰 날 즉흥 매매 자제
- **룰 어긋나면 즉시 정정** — 다음 weekly_review 에 인사이트 누적
- **현금이 옵션** (Buffett) — 무리한 진입보다 현금 보유 우선

> 케이스별 LLM 판단: signals.summary 중립 + 게이트 미통과 시 진입 보류. 강한매수만 진입.

---

## 9. 분산 vs 집중

**출처**: Warren Buffett (집중), Peter Lynch (적정 분산), Modern Portfolio Theory

핵심:
- **확신 있는 종목 = 집중** (포트 25% 룰 — Buffett 권장 한도)
- **불확실 = 분산** — 6~10 종목 권장 (개인 운영 규모)
- **상관계수 0.85+ 페어는 사실상 한 종목** — effective_holdings 추적
- **섹터 비중 30% 한도** — 한 섹터 집중 시 거시 충격에 취약

> 케이스별 LLM 판단: portfolio_correlation + detect_portfolio_concentration 결과 인용. check_concentration 게이트 통과 의무.

---

## 10. 회고와 학습

**출처**: Reminiscences of a Stock Operator (Lefèvre), Ray Dalio (Principles)

핵심:
- **모든 거래는 학습 sample** — 결과 무관 회고 의무
- **패턴 누적 → 자기만의 원칙 형성** — weekly_review 의 자연어 인사이트
- **weekly_review 가 학습의 본체** — 룰 win-rate / pattern_findings 추적
- **잘못된 판단도 정직하게 기록** — 자기 합리화 차단

> 케이스별 LLM 판단: per-stock-analysis 6단계에 weekly_context 인용 의무. 룰 win-rate < 30% 인 룰은 자제.

---

## 적용 원칙

| 룰 | 적용 |
|---|---|
| 위 10 원칙은 **출발점** | 케이스별 LLM 본문 판단으로 우선순위·강도 결정 |
| 구체 수치 (size/stop/threshold) | 박지 않음 — LLM 이 종목 / 산업 평균 / 변동성 따라 본문 판단 |
| 충돌 시 | LLM 이 reasoning 명시 — 어느 원칙을 우선 채택했는지 |
| 학습 누적 | weekly_review 의 자연어 인사이트 + rule_catalog win-rate 가 보강 |

→ 매트릭스 anchor 가 아닌 **방향성 출발점**. LLM 자율 추론 + 회고 학습이 본체.

---

## 관련 파일

- `references/per-stock-analysis.md` — 종목 1건 분석 단일 진입점 (6단계 LLM 판단에서 본 원칙 인용)
- `references/rule-catalog.md` — 매매 룰 카탈로그 (record_trade 시 분류)
- `references/_archive/` — 옛 매트릭스 (scoring-weights / decision-tree / position-action-rules) 참고용 보존
- `assets/daily-report-template.md` — 보고서 출력 (📐 Top-down 연결 섹션)
