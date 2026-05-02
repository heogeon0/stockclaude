# Stock Weekly Strategy

stock skill 의 **weekly-strategy 모드** 호출 (5번째 모드, v8 신설). 사용자 + LLM 협업 브레인스토밍으로 이번 주 매매 전략 수립.

## 동작

1. `~/.claude/skills/stock/SKILL.md` 의 룰 적용
2. `~/.claude/skills/stock/references/weekly-strategy-brainstorm.md` 의 5단계 절차 진입
3. 인자 처리:
   - `$ARGUMENTS` 가 비면 → 이번 주 (오늘 기준 월요일) 전략 수립
   - `$ARGUMENTS` 가 'YYYY-MM-DD' 면 → 해당 주 전략 수립

## 5 단계 절차

0. ⛔ BLOCKING — economy + industry base 신선도 체크 (`check_base_freshness`)
1. 인풋 수집 — 지난주 weekly_review + economy/industry base + 보유 종목 + learned_patterns + 지난 N주 strategies
2. LLM 1~3 전략 옵션 제시 (각 trade-off 명시, focus_themes / rules / risk_caps 정량 동반)
3. 사용자 검토 — 질문 / 시장 view / 옵션 수정 자유
4. 최종 합의 → `save_weekly_strategy` 호출

## 검증 필수

- 0단계 신선도 체크 누락 시 ⛔ 진입 차단
- 1~3 옵션 의무 (선택지가 협업의 핵심)
- 결과 검증 — `get_weekly_strategy()` read-back

## 위치

- 본 skill 본체: `~/.claude/skills/stock/`
- 절차서: `~/.claude/skills/stock/references/weekly-strategy-brainstorm.md`
- 학습 사이클 인풋:
  - 지난주 회고: `assets/weekly-review-template.md` (5번째 섹션 "이번 주 전략 평가")
  - 거장 원칙: `references/master-principles.md`
  - 일일 운영 인용: `references/per-stock-analysis.md` (6단계 인풋)
