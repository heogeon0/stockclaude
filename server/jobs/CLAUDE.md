# server/jobs/ — 배경 작업 (진입점 미상)

> 깊이 2 — jobs/ 폴더 진입 시 자동 로드.
> 3개 파일: `daily_snapshot.py / healthcheck.py / refresh_base.py`.

---

## ⚠️ 현재 상태 — 진입점 미확인

- 위 3개 파일이 존재하지만 **`server/main.py`·`server/mcp/server.py` 어디서도 import 안 보임**.
- cron / 스케줄러 / Procfile / nixpacks 등록 위치도 미확인.
- 사용 중인지·dead code인지 결정되지 않은 상태. **#16 GitHub 이슈로 추적 중**.

---

## 신규 작업 전 확인 룰

이 폴더에 코드 추가·수정 진입했다면, 먼저 사용 여부를 확인한다.

1. **호출 진입점 grep** — 프로젝트 전체에서 `from server.jobs` 또는 `import server.jobs` 검색.
2. **Procfile / nixpacks.toml** 확인 — release-phase / web / worker 프로세스 정의 있는지.
3. **외부 cron** — Railway scheduler / GitHub Actions / 시스템 crontab 등록 여부 확인.
4. 셋 다 미발견 → **사용자에게 사용 의도 확인 후 진행**. 임의 추가·수정 금지.

---

## 사용 중 확인 시

- 진입점을 명시 (어떤 프로세스가 어떤 스케줄로 호출하는지).
- 본 CLAUDE.md를 갱신해 진입점 표 추가.
- 신규 job 추가 시 동일하게 진입점 등록 의무.

## 미사용 확인 시

- 삭제 검토. 보존이 필요하면 `_archive/` 또는 git history만 의존.
- 미사용 dead code는 LLM에게 잘못된 컨텍스트 신호.

---

## 이슈 추적

- #16은 본 워커가 GitHub 이슈로 발행 — `chore(server/jobs): 사용 여부 확인 — 진입점 미상` (제목/링크는 W3·W7이 인덱스에 채움).
- 이슈 closing 후 본 CLAUDE.md를 사용 중/삭제 결과로 갱신.
