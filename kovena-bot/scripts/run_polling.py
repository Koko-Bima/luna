"""Локальный запуск бота для проверки — без Яндекс Облака и без вебхука.

Бот сам опрашивает Telegram (long polling), данные держит в памяти:
после перезапуска подписки, заказы и статистика обнуляются.

    pip install -r requirements.txt
    BOT_TOKEN=... python scripts/run_polling.py

ADMIN_IDS и OPERATOR_CHAT_ID можно не задавать: тогда первый, кто напишет
боту, станет и админом, и оператором (вопросы будут приходить ему же).
Перед запуском в облаке вебхук ставится заново — polling и webhook вместе не работают.
"""
from __future__ import annotations

import dataclasses
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bot.config import Config  # noqa: E402
from bot.context import Ctx  # noqa: E402
from bot.router import handle_update  # noqa: E402
from bot.telegram import Telegram, TelegramError  # noqa: E402
from db.memory import MemoryStore  # noqa: E402


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def main() -> None:
    os.environ.setdefault("WEBHOOK_SECRET", "polling")  # в polling не используется
    cfg = Config.from_env()
    auto_owner = not cfg.admin_ids
    bot = Telegram(cfg.bot_token, httpx.Client(timeout=40.0))
    store = MemoryStore()

    me = bot.call("getMe")
    info = bot.call("getWebhookInfo")
    if info.get("url"):
        sys.exit("У бота установлен вебхук — polling не получит сообщений. "
                 "Снимите его: deleteWebhook (в облаке бот тогда перестанет отвечать).")
    log(f"@{me['username']} запущен. Напишите ему /start в Telegram. Ctrl+C — остановить.")
    if auto_owner:
        log("ADMIN_IDS не задан: первый написавший станет админом и оператором.")

    offset = None
    while True:
        try:
            updates = bot.call("getUpdates", offset=offset, timeout=30,
                               allowed_updates=["message", "callback_query"])
        except (httpx.HTTPError, TelegramError) as e:
            log(f"ошибка связи с Telegram: {type(e).__name__}, повтор через 3 с")
            time.sleep(3)
            continue

        for upd in updates:
            offset = upd["update_id"] + 1
            sender = ((upd.get("message") or upd.get("callback_query") or {}).get("from") or {}).get("id")
            if auto_owner and sender:
                cfg = dataclasses.replace(cfg, admin_ids=frozenset({sender}), operator_chat_id=sender)
                auto_owner = False
                log(f"админ и оператор: id {sender}")
            kind = "кнопка" if "callback_query" in upd else "сообщение"
            try:
                handle_update(upd, Ctx(bot=bot, cfg=cfg, store=store))
                log(f"{kind} от id {sender}: обработано")
            except Exception as e:  # noqa: BLE001
                # Текст ошибки httpx содержит URL с токеном — печатаем только тип.
                detail = f": {e}" if isinstance(e, TelegramError) else ""
                log(f"{kind} от id {sender}: ошибка {type(e).__name__}{detail}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("остановлен")
