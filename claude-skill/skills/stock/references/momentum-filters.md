# 모멘텀 진입 / 청산 / Crash 방어 룰 (momentum 흡수)

> 로드 시점: 모멘텀 시그널 종합 후 액션 결정 시.

## 진입 필터 (AND 조건 — 5가지 모두 충족)

```
1. 시장 국면 모멘텀_가동 = True
   detect_market_regime() 결과
2. 종목 Dual Momentum = "Buy"
   absolute (12M vs 무위험) AND relative (벤치 대비)
3. 모멘텀 점수 70+
   rank_momentum 결과
4. 모멘텀 피로도 "초기" or "중기"
   180일 초과 시 신규 진입 중단
5. 거래량 동반
   20일/60일 비율 1.0+
```

## 청산 필터 (OR 조건 — 1가지만 발생해도 청산 검토)

```
1. 시장 국면 모멘텀_가동 = False
2. Dual Momentum = "Cash"
3. 모멘텀 점수 50 미만 + 순위 50 밖
4. 섹터 순위 하위 3
5. 180일 초과 지속 + 거래량 감소
```

## Momentum Crash 방어

| 트리거 | 행동 |
|---|---|
| **Breadth < 0.5** | 신규 진입 50% 축소 |
| **Breadth < 0.3** | 신규 진입 중단 |
| **V-KOSPI > 40** (KR) / **VIX > 30** (US) | 신규 진입 중단 |
| **KOSPI 10M MA 이탈** | **전면 방어 전환** — 현금 비중 50%+, 보유 손절선 타이트 |
| **연방 yield curve 역전** (US) | 신규 진입 보류 |

## 진입 의사결정 (research 결과 활용)

stock-discover 또는 stock-research 호출 결과의 6차원 종합 후:

```
IF 모든 진입 필터 충족
   AND 재무 등급 ≥ B
   AND 기술 verdict in (강한매수, 매수우세)
   AND 수급 신호 = 매집 또는 엇갈림
THEN 진입 후보
```

## 청산 의사결정

```
IF 청산 필터 1개 이상 발생
   AND (
     기술 verdict in (매도우세, 강한매도)
     OR 수급 = 강분산 z-2.0-
     OR 이벤트 = rating downgrade
   )
THEN 청산 후보
```

## 단계별 청산 (변동성×재무 매트릭스)

청산 트리거 발생 시 일괄 매도가 아니라 **셀별 단계 매도**:

- → `~/.claude/skills/stock/references/scoring-weights.md` 의 손절폭 / 피라미딩 단계 룰 참조
- 변동성 normal × A급 → 1차 손절선에서 50% 매도, 2차에서 잔여
- 변동성 extreme × D급 → 1차 손절선에서 전량 (타이트)

## 시장 국면 Off 시 일괄 행동

`detect_market_regime` 결과 모멘텀_가동 = False:

1. **신규 매수 전면 중단** (research / discover 결과 무관)
2. 보유 종목:
   - 모멘텀 점수 50+ → 홀딩 + 손절선 타이트화
   - 모멘텀 점수 50- → 즉시 청산 검토
3. 현금 비중 50%+ 유지

## 일일 추적 시 활용

stock-daily 의 종목별 분석 후:
- 진입 필터 / 청산 필터 / Crash 트리거 점검
- 결과를 daily 보고서 "📌 모멘텀 평가" 섹션에 기록
- 충족된 필터에 따라 액션 플랜 결정
