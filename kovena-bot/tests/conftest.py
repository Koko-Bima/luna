import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.config import Config  # noqa: E402
from db.memory import MemoryStore  # noqa: E402


class FakeBot:
    """Записывает вызовы Bot API. fail — исключение на любой вызов;
    fail_for — {chat_id: исключение} только для отправки этому чату."""

    def __init__(self, fail=None, fail_for=None):
        self.calls = []
        self.fail = fail
        self.fail_for = fail_for or {}

    def call(self, method, **params):
        if self.fail:
            raise self.fail
        err = self.fail_for.get(params.get("chat_id"))
        if err and method == "sendMessage":
            if callable(err):
                err = err(params)
            if err:
                raise err
        self.calls.append((method, params))

    def send_message(self, chat_id, text, reply_markup=None, **kw):
        self.call("sendMessage", chat_id=chat_id, text=text, reply_markup=reply_markup, **kw)

    @property
    def sent(self):
        return [p for m, p in self.calls if m == "sendMessage"]

    def sent_to(self, chat_id):
        return [p for p in self.sent if p["chat_id"] == chat_id]


class Clock:
    def __init__(self, dt):
        self.dt = dt

    def __call__(self):
        return self.dt

    def advance(self, **kw):
        self.dt += timedelta(**kw)


@pytest.fixture
def clock():
    # 14.11.2026 12:00 МСК — рабочее время.
    return Clock(datetime(2026, 11, 14, 9, 0, tzinfo=timezone.utc))


@pytest.fixture
def cfg():
    return Config(bot_token="123:abc", webhook_secret="s3cret", operator_chat_id=-1001,
                  admin_ids=frozenset({7}), promo_code="TELEGA5")


@pytest.fixture
def bot():
    return FakeBot()


@pytest.fixture
def store(clock):
    return MemoryStore(clock=clock)
