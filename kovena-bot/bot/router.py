"""Разбор апдейта и диспетчеризация."""
from __future__ import annotations

from bot import menu
from bot.config import Config
from content import texts


def parse_command(text: str) -> tuple[str, str] | None:
    """'/start@kovena_bot payload' -> ('start', 'payload')."""
    if not text.startswith("/"):
        return None
    head, _, rest = text.partition(" ")
    name = head[1:].split("@", 1)[0].lower()
    return name, rest.strip()


def handle_update(update: dict, bot, cfg: Config) -> None:
    if "message" in update:
        _on_message(update["message"], bot, cfg)
    elif "callback_query" in update:
        bot.call("answerCallbackQuery", callback_query_id=update["callback_query"]["id"])


def _on_message(msg: dict, bot, cfg: Config) -> None:
    chat = msg.get("chat", {})
    # Работаем только в личке. Чат оператора и любые группы — не наше дело.
    if chat.get("type") != "private":
        return
    chat_id = chat["id"]
    text = msg.get("text")

    if text is None:
        bot.send_message(chat_id, texts.NOT_UNDERSTOOD)
        return

    cmd = parse_command(text)
    if cmd:
        name, _arg = cmd
        if name in ("start", "menu", "help"):
            menu.send_menu(bot, chat_id)
            return
        # /zakaz, /promo, /podpiska и админ-команды — этапы 4–5.

    # Кнопки разделов и поиск по ключевым словам (C3) — этапы 2–3.
    bot.send_message(chat_id, texts.NOT_UNDERSTOOD)
