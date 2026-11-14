from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from bot.config import Config

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Ctx:
    bot: Any
    cfg: Config
    store: Any
    now: Callable[[], datetime] = field(default=utcnow)

    def local(self, dt: datetime | None = None) -> datetime:
        """Время в часовом поясе заказчика (TZ), независимо от пояса функции."""
        dt = dt or self.now()
        try:
            tz = ZoneInfo(self.cfg.tz)
        except Exception:  # нет базы часовых поясов — Москва без перехода на летнее время
            tz = timezone(timedelta(hours=3))
        return dt.astimezone(tz)

    def is_admin(self, tid: int | None) -> bool:
        return tid is not None and tid in self.cfg.admin_ids
