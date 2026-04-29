# Base Industry

stock skill 의 **base-industry 갱신** 호출 (사용자 명시 호출). 메인 LLM 이 sub-agent spawn.

## 동작

1. `~/.claude/skills/stock/SKILL.md` 의 base 갱신 정책 적용
2. `Agent("base-industry-updater", name="$ARGUMENTS")` spawn
3. sub-agent 정의: `~/.claude/skills/stock/agents/base-industry-updater.md`
4. 종료 후 메인이 `get_industry(code)` 로 DB 검증

## 인자

- `$ARGUMENTS`: 산업 코드 (필수)
  - KR 한글 슬러그: `반도체`, `게임`, `전력설비`, `금융지주`, `2차전지`, `AI-PCB`
  - US: `us-tech`, `us-communication`, `us-financials`, ...

## 절차

1. `Agent("base-industry-updater", name="...")` spawn
2. 결과 받음 + DB updated_at 검증
3. 사용자 보고 + 핵심 변경 (점유율 / 규제 / M&A 변화 등)

## 위치

- sub-agent: `~/.claude/skills/stock/agents/base-industry-updater.md`
- 템플릿: `~/.claude/skills/stock/assets/industry-base-template.md`
- 산업 분류: `~/.claude/skills/stock/references/industry-sectors.md`
