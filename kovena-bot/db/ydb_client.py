"""Доступ к YDB serverless. Состояние только здесь — диск функции не сохраняется."""
from __future__ import annotations

import ydb

_INSERT_UPDATE = """
DECLARE $update_id AS Int64;
INSERT INTO processed_updates (update_id, at) VALUES ($update_id, CurrentUtcTimestamp());
"""

_DELETE_UPDATE = """
DECLARE $update_id AS Int64;
DELETE FROM processed_updates WHERE update_id = $update_id;
"""


class YdbStore:
    def __init__(self, endpoint: str, database: str):
        # В Cloud Function без переменных YDB_*_CREDENTIALS SDK берёт токен
        # сервисного аккаунта функции из сервиса метаданных.
        self._driver = ydb.Driver(
            endpoint=endpoint,
            database=database,
            credentials=ydb.credentials_from_env_variables(),
        )
        self._driver.wait(timeout=5, fail_fast=True)
        self._pool = ydb.QuerySessionPool(self._driver)

    def mark_processed(self, update_id: int) -> bool:
        """True — апдейт новый. False — уже обрабатывали.

        INSERT в YDB атомарно падает на существующем ключе, поэтому
        две параллельные доставки одного апдейта не пройдут обе.
        """
        try:
            self._pool.execute_with_retries(
                _INSERT_UPDATE, {"$update_id": (update_id, ydb.PrimitiveType.Int64)}
            )
        except ydb.issues.PreconditionFailed:
            return False
        return True

    def unmark(self, update_id: int) -> None:
        self._pool.execute_with_retries(
            _DELETE_UPDATE, {"$update_id": (update_id, ydb.PrimitiveType.Int64)}
        )
