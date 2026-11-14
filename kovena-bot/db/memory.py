"""Хранилище в памяти — для тестов. Повторяет поведение YdbStore."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

STATE_TTL = timedelta(minutes=30)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MemoryStore:
    def __init__(self, clock=utcnow):
        self.now = clock
        self.seen: set[int] = set()
        self.users: dict[int, dict] = {}
        self.orders: dict[str, dict] = {}
        self.questions: list[tuple[int, datetime]] = []
        self.hits: list[tuple[str, datetime]] = []
        self.drafts: dict[int, dict] = {}

    # --- processed_updates
    def mark_processed(self, update_id: int) -> bool:
        if update_id in self.seen:
            return False
        self.seen.add(update_id)
        return True

    def unmark(self, update_id: int) -> None:
        self.seen.discard(update_id)

    # --- users
    def _user(self, tid: int) -> dict:
        return self.users.setdefault(tid, {"telegram_id": tid, "first_seen": self.now(),
                                           "opted_in": False})

    def touch_user(self, tid: int) -> None:
        self._user(tid)["last_seen"] = self.now()

    def get_state(self, tid: int) -> str | None:
        u = self.users.get(tid) or {}
        st, at = u.get("state"), u.get("state_at")
        if st and at and self.now() - at <= STATE_TTL:
            return st
        return None

    def set_state(self, tid: int, state: str | None) -> None:
        u = self._user(tid)
        u["state"], u["state_at"] = state, (self.now() if state else None)

    def set_opt_in(self, tid: int, value: bool) -> None:
        u = self._user(tid)
        u["opted_in"] = value
        u["opted_in_at"] = self.now() if value else None

    def is_opted_in(self, tid: int) -> bool:
        return bool((self.users.get(tid) or {}).get("opted_in"))

    def count_subscribers(self) -> int:
        return sum(1 for u in self.users.values() if u.get("opted_in"))

    def subscribers_after(self, last_id: int, limit: int) -> list[int]:
        ids = sorted(t for t, u in self.users.items() if u.get("opted_in") and t > last_id)
        return ids[:limit]

    def mark_promo(self, tid: int) -> None:
        self._user(tid)["promo_issued_at"] = self.now()

    # --- orders
    def set_order_status(self, no: str, status: str) -> None:
        o = self.orders.setdefault(no, {"order_no": no, "telegram_id": None,
                                        "delivered_at": None, "review_asked_at": None})
        o["status"], o["updated_at"] = status, self.now()
        if status == "доставлен" and not o["delivered_at"]:
            o["delivered_at"] = self.now()

    def get_order(self, no: str) -> dict | None:
        o = self.orders.get(no)
        return dict(o) if o else None

    def set_order_asker(self, no: str, tid: int) -> None:
        if no in self.orders:
            self.orders[no]["telegram_id"] = tid

    def set_review_asked(self, no: str) -> None:
        self.orders[no]["review_asked_at"] = self.now()

    # --- statistics
    def add_question(self, tid: int) -> None:
        self.questions.append((tid, self.now()))

    def add_hit(self, section: str) -> None:
        self.hits.append((section, self.now()))

    def stats(self, days: int) -> dict:
        since = self.now() - timedelta(days=days)
        return {
            "users": sum(1 for u in self.users.values()
                         if u.get("last_seen") and u["last_seen"] >= since),
            "questions": sum(1 for _, at in self.questions if at >= since),
            "sections": Counter(s for s, at in self.hits if at >= since).most_common(),
            "subscribers": self.count_subscribers(),
            "promo": sum(1 for u in self.users.values()
                         if u.get("promo_issued_at") and u["promo_issued_at"] >= since),
        }

    # --- broadcast drafts
    def save_draft(self, admin_id: int, text: str) -> None:
        self.drafts[admin_id] = {"text": text, "last_id": 0, "sent": 0, "blocked": 0, "failed": 0}

    def get_draft(self, admin_id: int) -> dict | None:
        d = self.drafts.get(admin_id)
        return dict(d) if d else None

    def update_draft(self, admin_id: int, last_id: int, sent: int, blocked: int, failed: int) -> None:
        self.drafts[admin_id].update(last_id=last_id, sent=sent, blocked=blocked, failed=failed)

    def delete_draft(self, admin_id: int) -> None:
        self.drafts.pop(admin_id, None)
