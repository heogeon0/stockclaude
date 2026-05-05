# scripts/ — 마이그레이션·운영 스크립트

> 청중: 마이그레이션 추가·운영 스크립트 손대는 Claude.
> 깊이 1 / most-local 단일 출처. 본문 한국어, 식별자/SQL 영어.

---

## 1. 마이그레이션 파일명 룰

- 형식: `NN_<설명>.sql` — `NN`은 2자리 zero-pad.
- 빈 번호 OK (현 인벤토리도 `03/05/07/08~21` 비연속 — 비어 있어도 `12` 다음 `13` 사용).
- **절대 기존 번호 재사용 금지** — 이미 적용된 환경에선 `schema_migrations`가 skip하므로 변경이 무효가 됨. 데이터 손실/스키마 어긋남의 주된 원인.

## 2. idempotent 강제

신규 마이그레이션은 모두 idempotent해야 한다. 동일 파일 N회 실행해도 같은 결과.

```sql
CREATE TABLE IF NOT EXISTS xxx (...);
ALTER TABLE xxx ADD COLUMN IF NOT EXISTS yyy ...;
CREATE INDEX IF NOT EXISTS idx_xxx_yyy ON xxx (yyy);
DROP TABLE IF EXISTS old_xxx;
```

- DML(INSERT/UPDATE)은 `ON CONFLICT DO NOTHING` 또는 존재 체크 SELECT로 가드.
- `ENUM` 타입 변경 등 idempotent 보장 어려운 변경은 회피 — CHECK 제약 사용 (db/CLAUDE.md §3).

## 3. `schema_migrations` 추적

- `run_migrations.sh`가 미적용 파일만 적용. 적용 후 `schema_migrations(filename, applied_at)` 행 생성.
- 이미 적용된 파일을 **수정해도 무효** (위 §1 "재사용 금지" 이유).
- 잘못된 마이그레이션 정정은 새 번호로 forward-fix 마이그레이션 추가.

## 4. Railway release-phase 자동 실행

- `Procfile` + `nixpacks.toml`이 release 단계에 `bash scripts/run_migrations.sh` 호출.
- 배포 전 로컬에서 적용 검증 필수 (§6 체크리스트).

## 5. 운영 스크립트 인벤토리

| 스크립트 | 용도 |
|---|---|
| `run_migrations.sh` | 마이그레이션 실행기 (Railway release + 로컬 공용) |
| `install-claude-skill.sh` | `~/.claude/skills/stock` 심링크/복사 (개인 환경 설치) |
| `build-skills.sh` | `dist/stockclaude.zip` 패키징 (Anthropic 업로드 포맷) |
| `db_dump.sh` | `db/seed.sql` 백업 (실데이터, gitignore) |
| `db_restore.sh` | dump 복원 |
| `measure_websearch.py` | WebSearch 토큰·성공률 측정 (`tests/test_measure_websearch.py`가 검증) |
| `README.md` | 스크립트 사용법 한 곳 모음 |

- 운영 스크립트(.sh)는 시작 시 `set -euo pipefail` 권장 — 실패 시 즉시 중단.
- 외부 식별자는 **`stockclaude`** 로 수렴 (build zip 등). DB 이름·MCP 인스턴스명 잔재는 W7 발행 이슈에서 추적.

## 6. 새 마이그레이션 추가 체크리스트

1. `ls scripts/[0-9][0-9]_*.sql` 마지막 번호 확인 → 다음 빈 번호 결정.
2. `NN_<설명>.sql` 파일 생성. 본문 idempotent (§2).
3. **로컬 docker compose**에서 적용 확인:
   ```bash
   docker compose up -d
   bash scripts/run_migrations.sh
   ```
4. `schema_migrations` 행 생성 확인:
   ```sql
   SELECT * FROM schema_migrations WHERE filename = 'NN_<설명>.sql';
   ```
5. 영향받는 `repos/`·`analysis/`·`schemas/` 코드 동시 수정 (한 PR 권장).
6. 신규 컬럼이 응답에 노출되면 `web/src/types/api.ts` 수동 동기화 (server/schemas/CLAUDE.md #15 참조).
7. `db/schema.sql` 스냅샷 갱신 (선택, 누적 결과 미러링).

## 7. 운영 스크립트 수정 시 룰

- `install-claude-skill.sh` / `build-skills.sh` 는 사용자 환경(`~/.claude/skills/`)·산출물 이름에 영향 — 변경 시 README.md 같이 갱신.
- `db_dump.sh` / `db_restore.sh` 는 `db/seed.sql` 경로 가정. 경로 변경 시 db/CLAUDE.md §5와 같이 보정.
- skill zip 파일명은 `stockclaude.zip` 고정 (외부 식별자 수렴 결정).

## 8. 금지 사항

- 마이그레이션 안에서 `DROP TABLE` 만 단독 사용 — 운영에서 데이터 손실. 반드시 백업·승인 후, 별도 PR로 분리.
- `run_migrations.sh` 우회한 수동 SQL 적용 — `schema_migrations` 추적이 깨짐.
- 기존 마이그레이션 파일 in-place 수정 (§1·§3).
