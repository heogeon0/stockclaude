# .claude/commands/ — 슬래시 wrapper 룰

> 본 폴더는 **8 개 슬래시 커맨드 wrapper** 만 보유. 모두 stock skill 의 한 모드 진입점. **로직은 일절 두지 않는다** — skill 본체 (`.claude/skills/stock/`) 가 모든 워크플로우를 가짐.

---

## 1. wrapper 단일 책임

- 슬래시 입력 (`/stock-daily`, `/base-economy` 등) → stock skill 의 해당 모드 진입.
- frontmatter (이름·간단 설명) + 진입 안내 1~3줄.
- **금지** — 절차 본문, 룰 디테일, 출력 포맷, 매매 임계값, MCP 툴 리스트.

skill 본체가 모드 라우팅·워크플로우·룰을 다 가지므로 wrapper 는 *어디로 들어가는지* 만 명시.

---

## 2. 8 커맨드 인벤토리

| 커맨드 | 모드 | 진입점 reference |
|---|---|---|
| `/stock-daily` | daily | `references/daily-workflow.md` (BLOCKING 14 + 7-Phase) |
| `/stock-discover` | discover | `references/discover-workflow.md` |
| `/stock-research` | research | `references/research-workflow.md` |
| `/stock-weekly-strategy` | weekly-strategy | `references/weekly-strategy-brainstorm.md` (5단계) |
| `/stock-weekly-review` | weekly-review | `references/weekly-review-workflow.md` (4-Phase) |
| `/base-economy` | base 갱신 | `references/base-economy-update-inline.md` |
| `/base-industry` | base 갱신 | `references/base-industry-update-inline.md` |
| `/base-stock` | base 갱신 | `references/base-stock-update-inline.md` |

---

## 3. wrapper 본문 길이

- **30줄 이하 권장**. 30줄 넘으면 본문이 절차를 가지고 있다는 신호 — references/ 로 옮긴다.
- 인자 처리 (`$ARGUMENTS` 비면 전종목, 있으면 단일 종목 등) 는 OK — wrapper 단순 분기까지만.

---

## 4. 신규 커맨드 추가 체크리스트

1. **wrapper 파일 생성** — `.claude/commands/<name>.md`.
2. **frontmatter** — 짧은 이름·설명.
3. **진입 안내** — `~/.claude/skills/stock/SKILL.md` 의 해당 모드 진입 + references 경로 명시. 1~3줄.
4. **SKILL.md 라우팅 표 추가** — 새 모드면 `.claude/skills/stock/SKILL.md` 의 라우팅 표 + 자연어 추측 표에 행 추가.
5. **references 워크플로우 신설** — `.claude/skills/stock/references/<name>-workflow.md` 작성 (규약은 `references/CLAUDE.md` §1·§3·§11).
6. **assets 템플릿** — 출력 포맷 있으면 `.claude/skills/stock/assets/<name>-template.md` 신설.

---

## 5. wrapper 본문 표준 구성 (예: stock-daily)

wrapper 가 가져도 되는 항목:
- 모드 1줄 설명.
- skill 진입 + references 경로 (`~/.claude/skills/stock/SKILL.md`, `~/.claude/skills/stock/references/<name>.md`).
- 인자 처리 분기 (예: `$ARGUMENTS` 비면 전종목 / 종목명이면 단일).
- 검증 의무 (BLOCKING 미호출 시 ⚠️, base stale inline 진입, DB read-back 등) — 항목 나열만, 디테일 X.
- 위치 안내 (skill 본체·workflow·template 경로).

가지면 안 되는 항목:
- BLOCKING 룰 본문, Phase 본문, 매매 임계값, 출력 마크다운 포맷, MCP 툴 호출 리스트.

---

## 6. 외부 참고

- skill 본체 구조: `.claude/skills/stock/CLAUDE.md` (d3) — SKILL.md / references / assets 3계층.
- reference 작성 규약: `.claude/skills/stock/references/CLAUDE.md` (d4 — 가장 상세).

본 폴더에 절차·룰을 두지 않는다. wrapper 가 두꺼워지면 skill 본체로 옮긴다.
