# server/repos/ — DB access 레이어

> 깊이 2 — repos/ 폴더 진입 시 자동 로드.
> 24개 파일, 모두 PostgreSQL raw SQL로 도메인 테이블 1개씩 담당 (analyst/cash/economy/industries/learned_patterns/portfolio/portfolio_snapshots/positions/rule_catalog/score_weights/stock_base/stock_daily/stocks/trades/users/watch_levels/weekly_review_per_stock/weekly_reviews/weekly_strategy/...).

---

## 책임 — 단일 출입구

- **모든 DB 접근은 여기를 경유한다.** `server/api/`, `server/mcp/`, `server/analysis/` 어디든 raw SQL을 직접 들고 있으면 안 된다. repos 함수를 호출하거나 신규 함수를 추가한다.
- analysis/는 순수 계산만 (DB 의존 X). repos/가 fetch → analysis/에 dict/DataFrame으로 넘긴다.
- api/mcp는 repos 호출 결과를 받아 응답으로 가공 (환율 변환·포맷 등).

---

## 패턴 — psycopg + raw SQL + dict_row

- ORM 미사용. `psycopg`(v3) 직접 사용.
- 모든 커서는 `dict_row` row factory로 열려 있다 (`server/db.py:22` `kwargs={"row_factory": dict_row}`). `cur.fetchall()` 결과는 `list[dict]`.
- 트랜잭션 경계는 `get_conn()` 컨텍스트 매니저가 관리:

  ```python
  from server.db import get_conn

  def list_active_positions(user_id: str) -> list[dict]:
      with get_conn() as conn, conn.cursor() as cur:
          cur.execute(
              """
              SELECT code, qty, avg_price, status
                FROM positions
               WHERE user_id = %s AND status IN ('Active','Pending')
              """,
              (user_id,),
          )
          return cur.fetchall()
  ```

- 컨텍스트 종료 시 정상이면 자동 `commit`, 예외면 `rollback` (`server/db.py:43-45`). repos 함수는 명시적으로 `commit()` 부르지 말 것.
- 여러 statement를 하나의 트랜잭션으로 묶으려면 동일 `get_conn()` 블록 안에서 처리.

---

## user_id 필터 강제 (멀티테넌트)

- `db/schema.sql`의 모든 도메인 테이블은 `user_id FK`. dev/MCP-stdio는 단일 유저 fallback이지만(`STOCK_USER_ID` env, §4.9) 코드 자체는 멀티유저 전제.
- **모든 SELECT/UPDATE/DELETE에 `WHERE user_id = %s` 강제**. 누락 시 다른 사용자 데이터 노출 위험.
- 신규 INSERT는 `user_id` 컬럼 명시 의무.

---

## KST 타임존 패턴 (§4.1)

- 거래일 기준 비교는 항상 KST. PostgreSQL은 `TIMESTAMPTZ`로 저장 + 조회 시 캐스트:

  ```sql
  WHERE (executed_at AT TIME ZONE 'Asia/Seoul')::date = %s
  ```

- Python 측 datetime 비교는 `ZoneInfo("Asia/Seoul")` 명시. `datetime.now()` 그대로 금지 (서버 로컬 타임 의존).
- `week_start`도 KST 월요일 (`server/repos/weekly_strategy.py:24`).
- **현재 일관성 깨짐**: `server/repos/portfolio_snapshots.py:170`만 `datetime.now(tz=...timezone.utc)`로 UTC 사용. §10.3 이슈로 추적 중. **신규 코드는 KST 따른다**. 기존 라인 수정 시 의도 확인 후 결정.

---

## Decimal·datetime·numpy 처리

- repos 반환은 그대로 OK. PostgreSQL `NUMERIC` → Python `Decimal`, `TIMESTAMPTZ` → `datetime` 그대로 흘려보낸다.
- **JSON 직렬화 책임은 호출자(api/mcp)**. MCP 툴은 `_json_safe`/`_row_safe` 통과 의무 (`server/mcp/server.py:206`). API는 pydantic `response_model`이 변환.
- repos에서 미리 float·str 변환하지 말 것 — 정밀도 손실.

---

## positions 직접 수정 금지 (§4.6)

- `positions` 테이블은 `trades` insert 트리거가 자동 재계산. **`UPDATE positions ...` 직접 금지** (`db/schema.sql:11`).
- 잘못 기록된 포지션은 trade 보정으로 해결 (반대 방향 trade insert). `repos/positions.py`에는 read 함수만 있어야 한다.
- 새 repos 함수가 positions write를 필요로 하면 STOP — trade 경유로 재설계.

---

## rule_catalog는 SSoT (§5.5)

- 매매 룰 단일 진실은 `rule_catalog` 테이블 (`server/repos/rule_catalog.py`).
- markdown reference나 frontend의 `signals12.ts` 텍스트는 *사람이 읽기용*. 판단·win-rate 산출은 DB 경유.
- 신규 룰은 `register_rule` MCP 툴 → `repos/rule_catalog.py` write 함수. 다른 곳에 룰 텍스트 하드코딩 금지.

---

## 신규 repos 함수 추가 체크리스트

1. 파일 선택 — 도메인 테이블 1개당 1파일. 새 도메인이면 `<table>.py` 신설.
2. 함수 시그니처 — `def <verb>_<noun>(user_id: str, ...) -> list[dict] | dict | None`.
3. `with get_conn() as conn, conn.cursor() as cur:` 패턴.
4. SQL — `%s` 파라미터 바인딩 (문자열 포맷팅 금지). user_id 필터 포함.
5. 거래일 비교는 `(col AT TIME ZONE 'Asia/Seoul')::date`.
6. 반환은 `cur.fetchall()` / `cur.fetchone()` 그대로 (dict_row가 변환).
7. 호출자(api/mcp)가 JSON-safe 변환 책임.
8. positions write는 금지 — trade 경유 확인.
