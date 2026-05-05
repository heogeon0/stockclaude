# tests/ — 테스트 가이드 (깊이 1)

> **목적**: 신규 테스트 추가 진입한 Claude를 위한 현 상태·룰·이슈 안내.
> **청중**: MCP 툴/repos/analysis 변경 후 검증 수단을 찾는 Claude.

---

## 1. 현 상태

- 유일한 테스트: `tests/test_measure_websearch.py` (203줄). `scripts/measure_websearch.py` 집계 함수만 검증.
- **핵심 비즈니스 로직 0% 커버** — 88 MCP 툴 / 24 repos / 16 analysis 모듈 / 13 API 라우터 모두 무테스트.
- 빠른 smoke 루프 부재. `uv run pytest tests/`는 0초로 끝나지만 거의 아무것도 검증 안 함.
- CI 미구성. `.github/workflows/`, `.gitlab-ci.yml` 둘 다 부재.
- DB 의존 테스트 없음. 현재 테스트는 synthetic dict로만 검증.

---

## 2. 환경

- pytest 8.3 + pytest-asyncio (`asyncio_mode=auto`) + httpx. `pyproject.toml`의 `[tool.pytest.ini_options]` 참고.
- uv `dev` 그룹. 실행: `uv run pytest tests/`.
- conftest·픽스처 부재. 신규 작성 시 `tests/conftest.py`부터.

---

## 3. 신규 테스트 룰

신규 기능은 최소 smoke 테스트 1개를 함께 추가한다. Claude가 30초 안에 자가검증 가능해야 한다.

- **MCP 툴 추가/수정**: 입력 1건에 대해 반환이 JSON-safe + 필수 키 존재만 확인하는 smoke 1개. `_json_safe`/`_row_safe` 통과 여부도 같이 확인.
- **repos 추가/수정**: docker compose의 `Postgres` 의존 통합 테스트로 작성. user_id 필터 누락 같은 멀티테넌트 회귀를 잡는 케이스 우선.
- **analysis 추가/수정**: synthetic dict 또는 OHLCV DataFrame 1건으로 deterministic 검증. DB 의존 금지(레이어 룰 — `server/analysis/CLAUDE.md` 참고).
- **scrapers**: 외부 API 모의(monkeypatch / `respx`) 권장. 실제 호출 금지(rate-limit·인증 키 노출).

---

## 4. 픽스처 가이드 (신규)

- DB 의존 테스트는 `tests/conftest.py`에 `pg_conn` 픽스처를 두고 `docker-compose.yml`의 `stock-manger-pg` (오타 — #11 이슈 추적)에 연결.
- 단일 유저 fallback은 `STOCK_USER_ID` env로 주입. 픽스처에서 명시.
- 트랜잭션 롤백 패턴 — 각 테스트는 savepoint로 격리, 종료 시 ROLLBACK.
- 한글 컬럼 OHLCV는 `날짜/시가/고가/저가/종가/거래량` 표준. synthetic 생성 시 컨벤션 준수.
- KST 거래일 비교가 들어간 코드는 `freezegun` + `Asia/Seoul` 명시.

---

## 5. 마커 컨벤션 (권장 — 도입 시)

- `@pytest.mark.smoke` — 30초 이내 빠른 검증. CI/로컬 디폴트.
- `@pytest.mark.db` — docker compose Postgres 필요.
- `@pytest.mark.external` — 외부 API 의존 (기본 skip).
- 도입 후 `pyproject.toml`의 `markers` 등록 의무.

---

## 6. 이슈 추적

- #10 "MCP/repos smoke 테스트 도입 로드맵" — GitHub 이슈로 발행됨. 본 폴더 작업 전 이슈 본문 확인.
- 본 CLAUDE.md는 *현재 약한 상태에서의 가이드*. 인프라 도입 후 갱신 필요.

---

## 7. 신규 테스트 추가 체크리스트

- [ ] 변경한 레이어(MCP/repos/analysis/api) 1개 = smoke 1개 이상.
- [ ] DB 의존이면 `@pytest.mark.db` + 픽스처 사용. 외부 API면 `@pytest.mark.external` + 모의.
- [ ] 한글 컬럼 / KST / user_id 필터 컨벤션 준수.
- [ ] `uv run pytest tests/` 30초 이내 통과 확인.
- [ ] CI 도입 전이라도 PR description에 실행 결과 캡처.
