"""Доступ к YDB serverless. Состояние только здесь — диск функции не сохраняется.

Поведение повторяет db/memory.py (на нём идут тесты).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import ydb

from db.memory import STATE_TTL

T = ydb.PrimitiveType
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _dt(v) -> datetime | None:
    """Timestamp из YDB приходит либо int (мкс), либо datetime — в зависимости от настроек SDK."""
    if v is None:
        return None
    if isinstance(v, int):
        return _EPOCH + timedelta(microseconds=v)
    return v if v.tzinfo else v.replace(tzinfo=timezone.utc)


class YdbStore:
    def __init__(self, endpoint: str, database: str):
        # В Cloud Function без переменных YDB_*_CREDENTIALS SDK берёт токен
        # сервисного аккаунта функции из сервиса метаданных.
        self._driver = ydb.Driver(endpoint=endpoint, database=database,
                                  credentials=ydb.credentials_from_env_variables())
        self._driver.wait(timeout=5, fail_fast=True)
        self._pool = ydb.QuerySessionPool(self._driver)

    def _q(self, query: str, params: dict | None = None) -> list:
        """Выполнить запрос, вернуть строки первого набора результатов."""
        decl = "".join(f"DECLARE {k} AS {_yql_type(t)};\n" for k, (_, t) in (params or {}).items())
        res = self._pool.execute_with_retries(decl + query, params or {})
        return list(res[0].rows) if res else []

    # --- processed_updates
    def mark_processed(self, update_id: int) -> bool:
        """INSERT атомарно падает на существующем ключе: две параллельные
        доставки одного апдейта не пройдут обе."""
        try:
            self._q("INSERT INTO processed_updates (update_id, at) VALUES ($id, $now);",
                    {"$id": (update_id, T.Int64), "$now": (_now(), T.Timestamp)})
        except ydb.issues.PreconditionFailed:
            return False
        return True

    def unmark(self, update_id: int) -> None:
        self._q("DELETE FROM processed_updates WHERE update_id = $id;", {"$id": (update_id, T.Int64)})

    # --- users
    def touch_user(self, tid: int) -> None:
        # Два простых запроса вместо UPSERT + UPDATE в одном: YDB не даёт
        # менять таблицу дважды в одной транзакции.
        now = _now()
        rows = self._q("SELECT first_seen FROM users WHERE telegram_id = $tid;",
                       {"$tid": (tid, T.Int64)})
        if rows and rows[0].first_seen is not None:
            self._q("UPSERT INTO users (telegram_id, last_seen) VALUES ($tid, $now);",
                    {"$tid": (tid, T.Int64), "$now": (now, T.Timestamp)})
        else:
            self._q("""
                UPSERT INTO users (telegram_id, first_seen, last_seen, opted_in)
                VALUES ($tid, $now, $now, false);
            """, {"$tid": (tid, T.Int64), "$now": (now, T.Timestamp)})

    def get_state(self, tid: int) -> str | None:
        rows = self._q("SELECT state, state_at FROM users WHERE telegram_id = $tid;",
                       {"$tid": (tid, T.Int64)})
        if not rows or not rows[0].state:
            return None
        at = _dt(rows[0].state_at)
        return rows[0].state if at and _now() - at <= STATE_TTL else None

    def set_state(self, tid: int, state: str | None) -> None:
        self._q("UPSERT INTO users (telegram_id, state, state_at) VALUES ($tid, $st, $at);", {
            "$tid": (tid, T.Int64),
            "$st": (state, ydb.OptionalType(T.Utf8)),
            "$at": (_now() if state else None, ydb.OptionalType(T.Timestamp)),
        })

    def set_opt_in(self, tid: int, value: bool) -> None:
        self._q("UPSERT INTO users (telegram_id, opted_in, opted_in_at) VALUES ($tid, $v, $at);", {
            "$tid": (tid, T.Int64), "$v": (value, T.Bool),
            "$at": (_now() if value else None, ydb.OptionalType(T.Timestamp)),
        })

    def is_opted_in(self, tid: int) -> bool:
        rows = self._q("SELECT opted_in FROM users WHERE telegram_id = $tid;", {"$tid": (tid, T.Int64)})
        return bool(rows and rows[0].opted_in)

    def count_subscribers(self) -> int:
        rows = self._q("SELECT COUNT(*) AS n FROM users WHERE opted_in = true;")
        return int(rows[0].n)

    def subscribers_after(self, last_id: int, limit: int) -> list[int]:
        rows = self._q("""
            SELECT telegram_id FROM users
            WHERE opted_in = true AND telegram_id > $last
            ORDER BY telegram_id LIMIT $lim;
        """, {"$last": (last_id, T.Int64), "$lim": (limit, T.Uint64)})
        return [r.telegram_id for r in rows]

    def mark_promo(self, tid: int) -> None:
        self._q("UPSERT INTO users (telegram_id, promo_issued_at) VALUES ($tid, $now);",
                {"$tid": (tid, T.Int64), "$now": (_now(), T.Timestamp)})

    # --- orders
    def set_order_status(self, no: str, status: str) -> None:
        now = _now()
        cur = self.get_order(no)
        delivered = cur["delivered_at"] if cur else None
        if status == "доставлен" and delivered is None:
            delivered = now
        self._q("""
            UPSERT INTO orders (order_no, status, updated_at, delivered_at)
            VALUES ($no, $st, $now, $dl);
        """, {"$no": (no, T.Utf8), "$st": (status, T.Utf8), "$now": (now, T.Timestamp),
              "$dl": (delivered, ydb.OptionalType(T.Timestamp))})

    def get_order(self, no: str) -> dict | None:
        rows = self._q("""
            SELECT order_no, status, updated_at, telegram_id, delivered_at, review_asked_at
            FROM orders WHERE order_no = $no;
        """, {"$no": (no, T.Utf8)})
        if not rows:
            return None
        r = rows[0]
        return {"order_no": r.order_no, "status": r.status, "updated_at": _dt(r.updated_at),
                "telegram_id": r.telegram_id, "delivered_at": _dt(r.delivered_at),
                "review_asked_at": _dt(r.review_asked_at)}

    def set_order_asker(self, no: str, tid: int) -> None:
        self._q("UPDATE orders SET telegram_id = $tid WHERE order_no = $no;",
                {"$no": (no, T.Utf8), "$tid": (tid, T.Int64)})

    def set_review_asked(self, no: str) -> None:
        self._q("UPDATE orders SET review_asked_at = $now WHERE order_no = $no;",
                {"$no": (no, T.Utf8), "$now": (_now(), T.Timestamp)})

    # --- statistics
    def add_question(self, tid: int) -> None:
        self._q("UPSERT INTO questions (id, telegram_id, asked_at) VALUES ($id, $tid, $now);",
                {"$id": (uuid.uuid4().hex, T.Utf8), "$tid": (tid, T.Int64),
                 "$now": (_now(), T.Timestamp)})

    def add_hit(self, section: str) -> None:
        self._q("UPSERT INTO menu_hits (id, section, at) VALUES ($id, $s, $now);",
                {"$id": (uuid.uuid4().hex, T.Utf8), "$s": (section, T.Utf8),
                 "$now": (_now(), T.Timestamp)})

    def stats(self, days: int) -> dict:
        p = {"$since": (_now() - timedelta(days=days), T.Timestamp)}
        users = self._q("SELECT COUNT(*) AS n FROM users WHERE last_seen >= $since;", p)
        qs = self._q("SELECT COUNT(*) AS n FROM questions WHERE asked_at >= $since;", p)
        promo = self._q("SELECT COUNT(*) AS n FROM users WHERE promo_issued_at >= $since;", p)
        secs = self._q("""
            SELECT section, COUNT(*) AS n FROM menu_hits WHERE at >= $since
            GROUP BY section ORDER BY n DESC;
        """, p)
        return {"users": int(users[0].n), "questions": int(qs[0].n),
                "sections": [(r.section, int(r.n)) for r in secs],
                "subscribers": self.count_subscribers(), "promo": int(promo[0].n)}

    # --- broadcast drafts
    def save_draft(self, admin_id: int, text: str) -> None:
        self._q("""
            UPSERT INTO drafts (admin_id, text, last_id, sent, blocked, failed, created_at)
            VALUES ($a, $t, 0, 0, 0, 0, $now);
        """, {"$a": (admin_id, T.Int64), "$t": (text, T.Utf8), "$now": (_now(), T.Timestamp)})

    def get_draft(self, admin_id: int) -> dict | None:
        rows = self._q("SELECT text, last_id, sent, blocked, failed FROM drafts WHERE admin_id = $a;",
                       {"$a": (admin_id, T.Int64)})
        if not rows:
            return None
        r = rows[0]
        return {"text": r.text, "last_id": r.last_id, "sent": r.sent,
                "blocked": r.blocked, "failed": r.failed}

    def update_draft(self, admin_id: int, last_id: int, sent: int, blocked: int, failed: int) -> None:
        self._q("""
            UPDATE drafts SET last_id = $l, sent = $s, blocked = $b, failed = $f
            WHERE admin_id = $a;
        """, {"$a": (admin_id, T.Int64), "$l": (last_id, T.Int64), "$s": (sent, T.Int32),
              "$b": (blocked, T.Int32), "$f": (failed, T.Int32)})

    def delete_draft(self, admin_id: int) -> None:
        self._q("DELETE FROM drafts WHERE admin_id = $a;", {"$a": (admin_id, T.Int64)})


def _yql_type(t) -> str:
    if isinstance(t, ydb.OptionalType):
        return f"Optional<{_yql_type(t.item)}>"
    return str(t)
