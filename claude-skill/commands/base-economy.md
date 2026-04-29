# Base Economy

stock skill 의 **base-economy 갱신** 호출 (사용자 명시 호출). 메인 LLM 이 sub-agent spawn.

## 동작

1. `~/.claude/skills/stock/SKILL.md` 의 base 갱신 정책 적용
2. `Agent("base-economy-updater", market="kr"|"us")` spawn
3. sub-agent 정의: `~/.claude/skills/stock/agents/base-economy-updater.md`
4. 종료 후 메인이 DB read-back 검증

## 인자

- `$ARGUMENTS`:
  - `--kr` → market="kr"
  - `--us` → market="us"
  - `--all` 또는 비어있음 → 양쪽 다 spawn (병렬)

## 절차

1. (선택) `check_base_freshness(auto_refresh=False)` 로 stale 확인
2. `Agent("base-economy-updater", market=...)` spawn
3. 결과 받음 (`status, market, updated_at, key_changes`)
4. `get_economy_base(market)` 로 DB updated_at 검증
5. 검증 통과 시 사용자 보고 + 핵심 변경 3줄

## 위치

- sub-agent: `~/.claude/skills/stock/agents/base-economy-updater.md`
- 템플릿: `~/.claude/skills/stock/assets/economy-base-template.md`
