"""Конфигурация из переменных окружения (ТЗ, п. 3.3)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _ids(raw: str) -> frozenset[int]:
    return frozenset(int(x) for x in raw.replace(" ", "").split(",") if x)


@dataclass(frozen=True)
class Config:
    bot_token: str
    webhook_secret: str
    operator_chat_id: int | None = None
    admin_ids: frozenset[int] = field(default_factory=frozenset)
    work_hours: str = "10:00-21:00"
    tz: str = "Europe/Moscow"
    ydb_endpoint: str = ""
    ydb_database: str = ""
    site_url: str = "https://kovena.ru"
    promo_code: str = ""
    webapp_enabled: bool = False

    @classmethod
    def from_env(cls) -> "Config":
        env = os.environ
        op = env.get("OPERATOR_CHAT_ID", "").strip()
        return cls(
            bot_token=env["BOT_TOKEN"],
            webhook_secret=env["WEBHOOK_SECRET"],
            operator_chat_id=int(op) if op else None,
            admin_ids=_ids(env.get("ADMIN_IDS", "")),
            work_hours=env.get("WORK_HOURS", "10:00-21:00"),
            tz=env.get("TZ", "Europe/Moscow"),
            ydb_endpoint=env.get("YDB_ENDPOINT", ""),
            ydb_database=env.get("YDB_DATABASE", ""),
            site_url=env.get("SITE_URL", "https://kovena.ru").rstrip("/"),
            promo_code=env.get("PROMO_CODE", ""),
            webapp_enabled=env.get("WEBAPP_ENABLED", "false").lower() == "true",
        )
