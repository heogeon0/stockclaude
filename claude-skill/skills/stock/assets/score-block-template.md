# Score Block 표준 템플릿

> 로드 시점: base.md 상단 등급 블록 작성 시.
> base-stock 의 5단계 (Scoring 저장) 직후.

## 표준 출력

```markdown
## 📊 현재 등급 (YYYY-MM-DD)

- **가중총점**: XX.X → **{Premium / Standard / Cautious / Defensive}**
- **재무**: XX (compute_financials → 0-100)
- **산업**: XX (industries/{산업}/base.md meta)
- **경제**: XX (economy/base.md meta)
- **밸류**: XX (analyst_target_avg vs 현재가 → 업사이드 환산)
- **변동성**: {normal/high/extreme} (analyze_volatility(code).regime)
- **재무 등급**: {A/B/C/D} (재무 점수 → A 80+ / B 60+ / C 40+ / D <40)
- **셀 (변동성×재무)**: {셀명} → 진입 사이즈 / 피라미딩 / 손절폭 (`stock/references/scoring-weights.md` 참고)

### 액션 템플릿 (변동성×재무 매트릭스)

- 손절폭: -X%
- 피라미딩 단계: X단
- 홀딩 기준: {일목 전환선/기준선 이탈 등}
- 트레일링: {SMA20 / 기준선}
```

## 등급 매핑

| 가중총점 | 종합 등급 |
|---|---|
| 80+ | Premium |
| 60-79 | Standard |
| 40-59 | Cautious |
| <40 | Defensive |

## 재무 등급 매핑 (compute_financials → 0-100)

| 점수 | 재무 등급 | 의미 |
|---|---|---|
| 80-100 | **A** | 흑자 우량, ROE 15%+, 부채 적정 |
| 60-79 | **B** | 흑자 보통, ROE 5-15%, 부채 양호 |
| 40-59 | **C** | 소폭 흑자 / 적자 진입기, 이익질 의심 |
| <40 | **D** | 적자 지속, 부채 과다, 경고 다수 |

## 변동성 매핑 (analyze_volatility.regime)

| 실현 변동성 | regime | 의미 |
|---|---|---|
| <30% | **normal** | 안정 |
| 30-50% | **high** | 단기 변동 큼 |
| 50%+ | **extreme** | 전구 종목 — 손절 타이트 |

## 차등 적용 (변동성×재무 매트릭스 12셀)

→ 셀별 진입 사이즈 / 피라미딩 / 손절폭 / 홀딩 horizon: `~/.claude/skills/stock/references/scoring-weights.md` 참조 (정의처).

base-stock 은 **셀명만 명시** — 구체 액션 룰은 stock 허브에서 단일 정의 (DRY).

## 단타/스윙/중장기 폐지 (v17)

기존 `style: day-trade / swing / long-term` 분기는 **폐지**.
새 룰: 모든 종목 동일 룰 + 변동성×재무 매트릭스로 차등.
