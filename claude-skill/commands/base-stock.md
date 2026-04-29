# Base Stock

stock skill 의 **base-stock 갱신** 호출 (사용자 명시 호출). 메인 LLM 이 sub-agent spawn.

## 동작

1. `~/.claude/skills/stock/SKILL.md` 의 base 갱신 정책 적용
2. 의존성 cascade 체크 — economy / industry stale 시 먼저 spawn (메인이 순차)
3. `Agent("base-stock-updater", code="$ARGUMENTS")` spawn
4. sub-agent 정의: `~/.claude/skills/stock/agents/base-stock-updater.md`
5. 종료 후 메인이 `get_stock_context(code).base` 로 DB 검증

## 인자

- `$ARGUMENTS`: 종목 코드 (필수)
  - KR: 6자리 숫자 (예: `005930`) 또는 한글명 (예: `삼성전자`)
  - US: 티커 (예: `NVDA`, `GOOGL`, `AAPL`)
  - `--mode new` / `--mode refresh` (생략 시 자동 — base 존재 여부로 판단)

## 절차

1. `get_stock_context(code)` — 현재 base 존재 + 만기 확인
2. 의존성 cascade — economy / industry / stock 순서로 stale 한 base 먼저 spawn
3. `Agent("base-stock-updater", code="...")` spawn
4. 결과 받음 (`status, code, updated_at, grade, key_changes`)
5. DB read-back 검증 (Trust but verify)
6. 사용자 보고 — grade + 핵심 변경 3~5줄

## 위치

- sub-agent: `~/.claude/skills/stock/agents/base-stock-updater.md` (가장 무거움 — 9 섹션 풀 작성)
- 템플릿: `~/.claude/skills/stock/assets/base-stock-template.md`
- 컨센 추적: `~/.claude/skills/stock/references/analyst-consensus-tracking.md`
- 10 Key Points: `~/.claude/skills/stock/references/narrative-10-key-points.md`
