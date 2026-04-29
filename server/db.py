"""
PostgreSQL connection pool + 컨텍스트 헬퍼.
repos/ 레이어만 여기서 커서 획득. analysis·api 등은 repos 통해서 간접 접근.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from server.config import settings

pool: ConnectionPool = ConnectionPool(
    conninfo=settings.database_url,
    min_size=1,
    max_size=10,
    kwargs={"row_factory": dict_row},
    open=False,  # lazy; main.py의 startup 이벤트에서 open
)


def open_pool() -> None:
    if pool.closed:
        pool.open(wait=True)


def close_pool() -> None:
    if not pool.closed:
        pool.close()


@contextmanager
def get_conn() -> Iterator[Connection[Any]]:
    """트랜잭션 경계 포함. 예외 시 rollback, 정상 종료 시 commit."""
    with pool.connection() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
