# db/ — 스키마 설계 원칙

> 청중: 스키마 변경·seed 작업 진입한 Claude.
> 깊이 1 / most-local 단일 출처. 본문은 한국어, 식별자/SQL은 영어.

---

## 1. 분업 원칙 (절대 룰)

**서버 = deterministic, Claude = reasoning** (출처: `db/schema.sql:11`).

- 서버(레포·SQL·analysis): 정량 계산만. 점수·메트릭·집계.
- Claude: 본문 자연어·의미 부여·결론 추론.
- 신규 컬럼 설계 시 — **본문(reasoning)** 은 `TEXT` (마크다운), **메타(deterministic)** 는 `JSONB` 또는 `NUMERIC`/`TIMESTAMPTZ`. 둘을 한 컬럼에 섞지 말 것.

## 2. 멀티테넌트 — `user_id` FK 강제

- 모든 도메인 테이블은 `user_id UUID NOT NULL REFERENCES users(id)`.
- 신규 테이블도 예외 없음. 1인 운영이지만 스키마는 멀티테넌트 유지 (config의 `STOCK_USER_ID` fallback과 별개).
- `repos/`의 SELECT/UPDATE는 모두 `WHERE user_id = %s` 동반 — 인덱스도 `(user_id, ...)` 복합.

## 3. CHECK 제약 — enum은 CHECK로

- 예: `stocks.currency CHECK (currency IN ('KRW','USD'))`.
- `positions.status` ∈ {Active, Pending, Close} (Pending은 qty=0 이지만 base.md 보유 — daily 분석 대상, §4.4 참조).
- 신규 enum 도입 시 CHECK 사용. PostgreSQL `ENUM` 타입은 마이그레이션 비용 큼 — 회피.

## 4. TIMESTAMPTZ + KST 캐스트 (§4.1, #13 보강)

- 시각 컬럼은 **TIMESTAMPTZ**. 신규 컬럼도 동일.
- **거래일 기준 비교는 KST 강제**:
  ```sql
  (executed_at AT TIME ZONE 'Asia/Seoul')::date
  ```
  출처: `server/mcp/server.py:3311,3434`.
- 함정: `created_at::date` 등 캐스트 누락 시 서버 로컬/UTC 기준이 되어 거래일 한 칸 어긋남.
- 신규 SQL 작성 시 — 거래일·주(week)·월 비교 시 반드시 `AT TIME ZONE 'Asia/Seoul'` 통과.
- `week_start`는 KST 월요일 (`server/repos/weekly_strategy.py:24`).
- **불일치 추적**: `server/repos/portfolio_snapshots.py:170`만 UTC 사용 — 의도 확인 전까지 신규 코드는 KST 따름. (관련 GitHub 이슈는 W2가 발행.)

## 5. seed 분리

| 파일 | 추적 | 용도 |
|---|---|---|
| `db/seed.example.sql` | git 추적 | 데모·산업 분류 시드 |
| `db/seed.sql` | `.gitignore` | 실데이터 (개인 환경) |

- `scripts/db_dump.sh` 가 `seed.sql` 백업.
- 데모 추가 시 `seed.example.sql` 만 수정. 실데이터를 example에 흘리지 말 것.

## 6. positions 자동 재계산 트리거 (§4.6)

- `trades` insert → `positions` 자동 재계산 트리거 발화.
- **`positions` 직접 UPDATE 금지** — 잘못 기록된 trade는 보정 trade로 정정.
- 신규 컬럼이 positions에 추가되면 트리거 함수도 같이 갱신해야 함.

## 7. rule_catalog DB SSoT (§5.5)

- `rule_catalog` 테이블 = 매매 룰 단일 진실 (`server/repos/rule_catalog.py`).
- markdown reference의 룰 텍스트는 **사람 읽기용** — 판단·win-rate 산출은 DB가 SSoT.
- 신규 룰은 `register_rule` MCP 툴로 등록 (학습→격상→카탈로그 자동 확장).

## 8. JSONB 사용 가이드

- 본문 메타: `stock_base.fundamentals`, `daily_reports.key_factors`, `learned_patterns.pattern_meta` 등.
- 인덱스가 필요한 키는 `jsonb_path_ops` GIN 또는 expression index 고려.
- 자주 조회하는 키는 정식 컬럼으로 승격 (예: `stock_base` phase/momentum 컬럼 — `13_alter_base_phase_momentum.sql`).

## 9. 변경 절차

1. **schema.sql 직접 수정 X**. 항상 `scripts/NN_<설명>.sql` 마이그레이션 파일로.
2. 마이그레이션 idempotent + 번호 룰은 `scripts/CLAUDE.md` 참조.
3. schema.sql은 마이그레이션 누적 결과의 스냅샷 — 마이그레이션 적용 후 동기화.
4. CHECK·user_id FK·TIMESTAMPTZ 룰(§2·§3·§4)은 신규 테이블·컬럼에 동일 적용.

## 10. 자주 만나는 함정 요약

- 거래일 비교에서 `AT TIME ZONE 'Asia/Seoul'` 누락 → 한 칸 어긋난 일자 집계. (§4)
- `positions` 직접 UPDATE → 다음 trade insert로 트리거가 덮어 씀. (§6)
- `seed.example.sql`에 실데이터 흘림 → git에 개인 보유 종목 노출. (§5)
- markdown reference 룰을 보고 매매 판단 → DB `rule_catalog`와 silent drift. (§7)
- 신규 도메인 테이블에 `user_id` 누락 → 멀티테넌트 격리 깨짐, 추후 재마이그레이션 비용 큼. (§2)
