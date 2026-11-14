"""Точка входа Yandex Cloud Function: kovena-bot/handler.handler."""
from __future__ import annotations

import base64
import hmac
import json
import logging

from bot.config import Config
from bot.router import handle_update
from bot.telegram import Telegram, TelegramError

log = logging.getLogger("kovena")
log.setLevel(logging.INFO)

# Ошибки Telegram, при которых повтор бесполезен: бот заблокирован,
# чат не найден, неверный запрос. Апдейт считаем обработанным.
_FINAL_TG_CODES = {400, 403}

_app = None


def _resp(code: int) -> dict:
    return {"statusCode": code, "body": ""}


def _get_app():
    global _app
    if _app is None:
        from db.ydb_client import YdbStore

        cfg = Config.from_env()
        _app = (cfg, YdbStore(cfg.ydb_endpoint, cfg.ydb_database), Telegram(cfg.bot_token))
    return _app


def process(event: dict, cfg: Config, store, bot) -> dict:
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    got = headers.get("x-telegram-bot-api-secret-token", "")
    if not cfg.webhook_secret or not hmac.compare_digest(got.encode(), cfg.webhook_secret.encode()):
        return _resp(403)

    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    try:
        update = json.loads(body)
        update_id = int(update["update_id"])
    except (ValueError, KeyError, TypeError):
        return _resp(400)

    if not store.mark_processed(update_id):
        log.info("duplicate update %s skipped", update_id)
        return _resp(200)

    try:
        handle_update(update, bot, cfg)
    except TelegramError as e:
        if e.code in _FINAL_TG_CODES:
            log.warning("update %s: telegram %s", update_id, e.code)
            return _resp(200)
        store.unmark(update_id)
        log.error("update %s: telegram %s, will retry", update_id, e.code)
        return _resp(500)
    except Exception as e:  # noqa: BLE001
        # Только тип ошибки: в тексте исключения может оказаться
        # сообщение пользователя или URL с токеном.
        store.unmark(update_id)
        log.error("update %s failed: %s", update_id, type(e).__name__)
        return _resp(500)

    return _resp(200)


def handler(event, context):
    cfg, store, bot = _get_app()
    return process(event, cfg, store, bot)
