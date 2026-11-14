import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.config import Config  # noqa: E402


class FakeBot:
    def __init__(self, fail=None):
        self.calls = []
        self.fail = fail

    def call(self, method, **params):
        if self.fail:
            raise self.fail
        self.calls.append((method, params))

    def send_message(self, chat_id, text, reply_markup=None, **kw):
        self.call("sendMessage", chat_id=chat_id, text=text, reply_markup=reply_markup, **kw)

    @property
    def sent(self):
        return [p for m, p in self.calls if m == "sendMessage"]


class FakeStore:
    def __init__(self):
        self.seen = set()

    def mark_processed(self, update_id):
        if update_id in self.seen:
            return False
        self.seen.add(update_id)
        return True

    def unmark(self, update_id):
        self.seen.discard(update_id)


@pytest.fixture
def cfg():
    return Config(bot_token="123:abc", webhook_secret="s3cret")


@pytest.fixture
def bot():
    return FakeBot()


@pytest.fixture
def store():
    return FakeStore()
