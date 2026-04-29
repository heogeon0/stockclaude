# Stock Daily

stock skill 의 **daily 모드** 호출. 보유(Active) + 감시(Pending) 종목 일일 운영.

## 동작

1. `~/.claude/skills/stock/SKILL.md` 의 룰 적용
2. `~/.claude/skills/stock/references/daily-workflow.md` 의 BLOCKING 12 + v2 7-Phase 진입
3. 인자 처리:
   - `$ARGUMENTS` 가 비면 → portfolio 모드 (`list_daily_positions()` 전 종목)
   - `$ARGUMENTS` 가 종목명/티커면 → 단일 종목 모드

## 검증 필수

- BLOCKING 12개 (Phase 0~1) 다 호출하지 않으면 결과 최상단에 ⚠️ 반쪽 daily 명시
- base stale 감지 시 즉시 sub-agent spawn (`Agent("base-*-updater", ...)`)
- 결과 검증 — DB read-back (Trust but verify)

## 위치

- 본 skill 본체: `~/.claude/skills/stock/`
- 워크플로우: `~/.claude/skills/stock/references/daily-workflow.md`
- 출력 템플릿: `~/.claude/skills/stock/assets/daily-report-template.md`, `portfolio-summary-template.md`
