# Weekly Strategy Brainstorm — 사용자 + LLM 협업 절차

> stock skill 의 5번째 모드. 매주 월요일 (또는 사용자 명시 호출 시) `/stock-weekly-strategy` 진입.
> v8 (2026-05) 신설. 학습 사이클의 시작점.
>
> **절차 핵심**: LLM 이 인풋 종합 → 1~3 전략 옵션 제시 → 사용자 검토·수정 → 합의 후 저장.
> 사용자 자율 작성 X, **협업 브레인스토밍** 형태.

---

## 진입 조건

| 호출 | 의미 |
|---|---|
| 사용자 명시 `/stock-weekly-strategy` | 즉시 brainstorm 진입 (B 안 결정, 자동 트리거 X) |
| 월요일 daily 시 weekly_strategy 미작성 발견 | ⚠️ "이번 주 전략 미작성, carry-over 사용 중" 알림. 사용자 명시 호출 안내 |
| 미작성 + 직전 strategy 존재 | `get_weekly_strategy()` 가 carry_over=True 반환. 일일 운영 가능하지만 권장 X |
| 미작성 + 직전 strategy 없음 | 첫 주 — 즉시 brainstorm 진입 권장 |

---

## 5 단계 절차

### 0단계 ⛔ BLOCKING — economy + industry base 신선도 체크

> 시장/산업 관점이 stale 이면 전략 통째로 잘못된 가정 위에서 짭니다. 진입 전 강제 체크.

```python
check_base_freshness(auto_refresh=True)
```

확인 대상:
- `economy[market].is_stale` (KR + US 보유면 둘 다)
- `industries[]` 중 보유 + 관심 산업

stale 발견 시:
- economy stale → `references/base-economy-update-inline.md` 절차 실행
- industry stale → `references/base-industry-update-inline.md` 절차 실행
- ⚠️ 종목 base 는 본 절차에서 무시 (per-stock-analysis 책임)

> ⛔ "효율 우선" / "전략 먼저 쓰고 base 나중에" 같은 LLM 우회 패턴 차단. 전략 인풋의 정확성이 학습 사이클의 신뢰성을 결정.

### 1단계 — 인풋 수집

LLM 이 다음 데이터 일괄 조회:

```python
# 지난주 회고
last_review = get_weekly_review(prev_monday)
   → next_week_emphasize / next_week_avoid / lessons_learned 인용

# 매크로 / 산업
economy_kr = get_economy_base("kr")
economy_us = get_economy_base("us")  # 보유 시
for industry in 보유_관심_산업들:
    get_industry(industry)

# 보유 종목
positions = list_daily_positions()

# 학습 누적
learned = get_learned_patterns(status="user_principle") + get_learned_patterns(status="principle")

# 거장 원칙 (참조)
master_principles = Read("references/master-principles.md")

# 지난 N주 전략 누적 (사용자 행동 패턴 추출용)
prev_strategies = list_weekly_strategies(weeks=12)
```

### 2단계 — LLM 1~3 전략 옵션 제시

위 인풋 종합해서 **1~3 옵션** 제시. 각 옵션마다:

- **시장관** (자연어 1~2줄): "현재 경제 cycle_phase=정점 + 산업 RS 약세 → ..."
- **focus_themes**: 산업/테마 list (예: 반도체 / AI 인프라 / 방산)
- **rules_to_emphasize**: 강화 룰 ID list + 이유 (지난주 win_rate 인용)
- **rules_to_avoid**: 자제 룰 ID list + 이유 (win_rate < 30%)
- **position_targets**: 신규 후보 / 청산 후보 / 비중 (kr/us)
- **risk_caps**: single_trade_pct / sector_max / cash_min

**옵션 예시**:

| 옵션 | 시장관 | 신규 | 청산 | 현금 | 손절 |
|---|---|---|---|---|---|
| A. 방어 | 정점 → 수축 진입, risk-off | 0 | 1~2 | +20% | 타이트 |
| B. 균형 | 정점, 모멘텀 유지 시 보유 | 1~2 | 0 | 0 | 표준 |
| C. 공격 | 강세 지속 베팅 | 3~4 | 0 | -10% | 풀 |

각 옵션의 **trade-off** 명시 (예: 방어 = 상승 시 기회비용 vs 안전).

### 3단계 — 사용자 검토

사용자 입력 자유:
- 질문 / 의문점
- 시장 view 코멘트 ("나는 정점이 아니라 사이클 중간이라고 봄")
- 옵션 수정 요청 ("B 안에 반도체 비중 50% 로 강화하자")
- 새 옵션 D 제안

LLM 응답:
- 사용자 view 반영해서 옵션 갱신
- 새 옵션이 master-principles / learned_patterns 와 정합/충돌 여부 본문 판단
- 합의 시까지 반복

### 4단계 — 최종 합의

사용자 "이 옵션으로 가자" 또는 final 옵션 명시 시:

```python
save_weekly_strategy(
    week_start="YYYY-MM-DD",  # 이번 주 월요일
    market_outlook="...",      # 자연어
    focus_themes=["반도체", ...],
    rules_to_emphasize=[2, 5],
    rules_to_avoid=[8],
    position_targets={
        "신규": ["005930"],
        "청산": [],
        "비중": {"kr": 0.7, "us": 0.3}
    },
    risk_caps={
        "single_trade_pct": 1.5,
        "sector_max": 0.30,
        "cash_min": 0.20
    },
    notes="사용자 view: ...",
    brainstorm_log="<3 옵션 + 검토 대화 + 합의 과정 자유 텍스트>"
)
```

read-back 검증:
```python
strategy = get_weekly_strategy(week_start="YYYY-MM-DD")
assert strategy.approved_at > <save 직전 시각>
```

---

## 학습 사이클 닫기

```
[월요일] weekly_strategy brainstorm (본 절차)
    ↓ (1주일)
[화~금] 일일 운영 — per-stock-analysis 가 weekly_strategy 인용
    ↓
[금/주말] weekly_review 작성 — assets/weekly-review-template.md 의 "이번 주 전략 평가" 섹션:
    · focus_themes 적중 / 실패
    · rules_to_emphasize 의 win-rate
    · rules_to_avoid 자제 효과
    · 다음 주 시사점
    ↓
[다음 월요일] 또 brainstorm — 1단계 인풋의 last_review + prev_strategies 가 본 review 인용
```

---

## 자율 우회 금지

- ⛔ "이번 주는 바쁘니 carry-over 로 가자" — 사용자 명시 승인 없이는 brainstorm 회피 X
- ⛔ "옵션 1개만 제시" — 1~3 옵션 의무 (선택지 + trade-off 가 협업의 핵심)
- ⛔ "정량 없이 자연어만" — focus_themes / rules / risk_caps 정량 동반 의무

---

## 관련 파일

- `references/master-principles.md` — 거장 원칙 (1단계 인풋)
- `references/per-stock-analysis.md` — 일일 운영 시 weekly_strategy 인용 (6단계 인풋)
- `assets/weekly-review-template.md` — 주간 회고 (5번째 섹션 "이번 주 전략 평가" 가 학습 사이클 닫음)
- `references/rule-catalog.md` — 룰 ID 정의 (rules_to_emphasize / rules_to_avoid 인용)
- `commands/stock-weekly-strategy.md` — 사용자 진입 wrapper
