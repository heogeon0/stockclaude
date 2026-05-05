# server/api/ — REST 라우터 가이드

## 책임

13 REST 라우터를 보유. 각 파일 = 1 도메인 리소스. FastAPI `APIRouter`로 모듈화 후 `server/main.py`에서 `app.include_router(...)` 등록.

현 인벤토리:
- `portfolio.py` / `trades.py` / `stocks.py` / `daily_reports.py`
- `industries.py` / `economy.py` / `regime.py`
- `score_weights.py` / `backtest.py`
- `skills.py` / `weekly_reviews.py`
- `deps.py` (인증 의존성, 라우터 X)
- `__init__.py`

## 1 라우터 = 1 리소스

본문은 1개 도메인만. 다른 리소스 데이터가 필요해도 그쪽 라우터로 가지 말고 같은 `repos/`를 직접 호출.

```python
# good: portfolio.py 안에서 trades 도 호출 (같은 repos 경유)
from server.repos import cash, portfolio, positions, trades
```

```python
# bad: 다른 라우터 함수 직접 호출
from server.api.trades import list_trades  # NO
```

## prefix·tags·dependencies 컨벤션

`APIRouter` 생성 시 셋 다 명시. 통일 패턴:

```python
router = APIRouter(
    prefix="/portfolio",
    tags=["portfolio"],
    dependencies=[Depends(require_google_user)],
)
```

- **prefix**: 리소스 단수형 또는 복수형 (현 인벤토리 보고 follow). 예: `/portfolio`, `/trades`, `/stocks`, `/daily-reports`.
- **tags**: 리소스명 그대로 (OpenAPI 그룹핑).
- **dependencies**: `require_google_user`를 라우터 레벨에 박아서 핸들러마다 반복 X.

## 인증 의존성 (server/api/deps.py)

3개 함수:
- `verify_google_id_token(token) -> email | None` — Google JWKS 서명 + aud + iss + 만료 + email_verified 검증.
- `require_google_user(authorization)` — Bearer 헤더 검증 + `ALLOWED_EMAILS` 화이트리스트. **dev 모드 + 토큰 없음 → "dev@localhost" 통과** (로컬 편의).
- `current_user_id(email = Depends(require_google_user)) -> UUID` — email→`users` 테이블 lookup (없으면 자동 생성). dev 더미는 `settings.stock_user_id` fallback.

핸들러는 보통 `user_id: UUID = Depends(current_user_id)`만 받음. 라우터 레벨에서 `require_google_user`가 이미 박혔으니 401/403은 거기서 끊김.

## response_model 룰

- 응답은 반드시 `server/schemas/*` pydantic 모델 사용.
- 명명: `XxxOut` (응답), `XxxIn` (요청). 필드는 snake_case (FastAPI가 그대로 직렬화).
- `Optional` 명시: null 허용 시 명시 — 누락 시 frontend 깨짐.

```python
@router.get("", response_model=PortfolioOut)
def get_portfolio(
    status: PositionStatus = "active",
    user_id: UUID = Depends(current_user_id),
) -> PortfolioOut:
    ...
    return PortfolioOut(positions=..., cash=..., kr_total_krw=..., ...)
```

**수동 동기화 의무 (§10.5)**: 응답 필드 추가/변경 시 `web/src/types/api.ts`도 같이 수정. 현재 자동 생성(openapi-typescript) 미적용 — silent drift 위험. 자동화 도입은 §10.5 이슈로 추적.

## 직접 SQL 금지 — repos 경유

api 라우터 안에서 `cur.execute("SELECT ...")` 또는 `get_conn()` 직접 사용 X. 반드시 `server.repos.<module>`의 함수 호출.

```python
# good
from server.repos import positions, trades, cash, portfolio
data = portfolio.compute_current_weights(user_id)

# bad
with get_conn() as conn:
    conn.execute("SELECT * FROM positions WHERE user_id = %s", [user_id])  # NO
```

이유: (a) user_id 필터 강제 (b) Decimal/datetime 처리 일관 (c) 스키마 변경 시 한 곳만 수정.

## 환율 변환 위치

**API 단에서만** 수행 — MCP는 unconverted 반환. 통화 단위 섞임 방지 (research §4.3).

- `stocks.currency` ∈ ('KRW','USD'). `cash_balance`도 currency별 별도 행.
- KR/US 합산이 필요한 응답은 라우터 안에서 환율 적용 후 같은 단위로 반환.
- pydantic 모델에 `kr_total_krw / us_total_usd` 처럼 **단위 명시 필드**로 분리하면 더 안전 (예: `PortfolioOut`).

## Pending vs Active (research §4.4)

- `get_portfolio` (FastAPI)는 `status` query param: `"active"`(default) | `"all"`.
- daily 워크플로우 데이터를 web에 노출할 때는 `positions.list_all(user_id)` 사용 (Active+Pending+Close 구분 가능 컬럼 포함).
- MCP의 `get_portfolio()`는 Active만 — 라우터 응답과 의미가 다름. 혼동 방지.

## 신규 라우터 추가 체크리스트

1. `server/api/<resource>.py` 생성 — `router = APIRouter(prefix="/<resource>", tags=[...], dependencies=[Depends(require_google_user)])`.
2. `server/schemas/<resource>.py`에 `XxxOut/XxxIn` pydantic 모델 추가.
3. `web/src/types/api.ts`에 동일 타입 미러링 (수동 동기화).
4. 핸들러에 `user_id: UUID = Depends(current_user_id)` 주입.
5. SQL은 `server/repos/`를 통해서만.
6. KR/US 합산이면 환율 변환은 라우터 안에서.
7. `server/main.py`의 `from server.api import (...)`에 추가하고 `app.include_router(<resource>.router)` 호출.
8. `web/src/hooks/use<Resource>.ts` 추가 (1훅 = 1엔드포인트, queryKey 일관 — `web/src/hooks/CLAUDE.md` 참조).

## 예시 패턴 — portfolio.py

```python
router = APIRouter(prefix="/portfolio", tags=["portfolio"],
                   dependencies=[Depends(require_google_user)])

@router.get("", response_model=PortfolioOut)
def get_portfolio(status: PositionStatus = "active",
                  user_id: UUID = Depends(current_user_id)) -> PortfolioOut:
    data = portfolio.compute_current_weights(user_id)   # repos 경유
    realized = trades.total_realized_by_market(user_id)
    return PortfolioOut(positions=..., cash=data["cash"], ...)
```

`server/api/portfolio.py:24-57` 그대로 발췌. 다른 라우터도 같은 골격.
