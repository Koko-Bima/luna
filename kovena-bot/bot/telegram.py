"""Тонкий клиент Bot API на httpx.

Не логирует ни параметры запросов (там тексты пользователей), ни URL (там токен).
"""
from __future__ import annotations

import httpx


class TelegramError(Exception):
    def __init__(self, code: int | None, description: str):
        super().__init__(f"{code}: {description}")
        self.code = code
        self.description = description


class Telegram:
    def __init__(self, token: str, client: httpx.Client | None = None):
        self._base = f"https://api.telegram.org/bot{token}/"
        self._client = client or httpx.Client(timeout=5.0)

    def call(self, method: str, **params):
        params = {k: v for k, v in params.items() if v is not None}
        resp = self._client.post(self._base + method, json=params)
        data = resp.json()
        if not data.get("ok"):
            raise TelegramError(data.get("error_code"), data.get("description", ""))
        return data.get("result")

    def send_message(self, chat_id: int, text: str, reply_markup: dict | None = None, **kw):
        return self.call("sendMessage", chat_id=chat_id, text=text, reply_markup=reply_markup, **kw)
