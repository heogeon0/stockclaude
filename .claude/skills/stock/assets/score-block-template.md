# Score Block 표준 템플릿 (v6, 매트릭스 폐기 후)

> 로드 시점: base.md 상단 등급 블록 작성 시.
> base-stock 의 5단계 (Scoring 저장) 직후.

## 표준 출력

```markdown
## 📊 현재 등급 (YYYY-MM-DD)

- **가중총점**: XX.X → **{Premium / Standard / Cautious / Defensive}**
- **재무**: XX (compute_financials → 0-100, 1차 필터용)
- **산업**: XX (industries/{산업}/base.md meta)
- **경제**: XX (economy/base.md meta)
- **밸류**: XX (analyst_target_avg vs 현재가 → 업사이드 환산)
- **변동성 regime**: {normal/high/extreme} (`analyze_volatility(code).regime`)
- **재무 grade**: {A/B/C/D} — 산업 평균 대비 본문 판단 (`industries.avg_per/avg_pbr/avg_roe/avg_op_margin` 인용)

### 액션 결정 (LLM 본문 판단)

- 손절폭 / 피라미딩 / 홀딩 / 트레일링 — `~/.claude/skills/stock/references/master-principles.md` 10 카테고리 인용 (손익 관리 / 추세 추종 / 변동성 관리 / 사이클 인식)
- 변동성 regime + 재무 grade + 산업 평균 + Top-down 정합성 종합 본문 판단
- 옛 매트릭스 룩업 (`_archive/scoring-weights.md`) anchor 효과로 v6 폐기 — 인용 X
```

## 등급 매핑

| 가중총점 | 종합 등급 |
|---|---|
| 80+ | Premium |
| 60-79 | Standard |
| 40-59 | Cautious |
| <40 | Defensive |

> ⚠️ 점수는 **discover/screen 의 빠른 1차 필터용**. 종목 1건 분석에서는 본문 (ratios + growth + 산업·경제 컨텍스트) 보고 LLM 판단 우선 — 점수 anchor 금지.

## 재무 grade 결정 (산업 평균 대비, v6)

절대값 anchor 금지. 산업 평균 대비 본문 판단:

| grade | 의미 (산업 평균 대비) |
|---|---|
| **A** | PER/PBR 할인 + ROE 산업 평균 상회 + 영업이익률 상위 + 성장 모멘텀 |
| **B** | 평균 수준, 일부 우월/일부 평균 |
| **C** | 평균 미달 차원 다수, 이익 질 의심 |
| **D** | 산업 평균 대비 큰 폭 열위, 적자/부채 과다, 경고 다수 |

산업 표준 메트릭은 `compute_industry_metrics(industry_code)` 1회로 자동 산출.

## 변동성 regime 매핑 (analyze_volatility.regime)

| 실현 변동성 | regime | 의미 |
|---|---|---|
| <30% | **normal** | 안정 |
| 30-50% | **high** | 단기 변동 큼 |
| 50%+ | **extreme** | 전구 종목 — 손절 타이트 권장 (LLM 본문 판단) |

## 단타/스윙/중장기 폐지 (v17)

기존 `style: day-trade / swing / long-term` 분기는 **폐지**.
모든 종목 동일 룰 + 산업 평균 대비 + LLM 본문 판단으로 차등 (master-principles 인용).
