"""Разбор апдейта и диспетчеризация."""
from __future__ import annotations

from bot import menu, sections
from bot.config import Config
from content import texts

BUTTONS = {
    texts.BTN_NABORY: sections.send_nabory,
    texts.BTN_SOSTAV: sections.send_sostav,
    texts.BTN_DOSTAVKA: sections.send_dostavka,
    texts.BTN_VOZVRAT: sections.send_vozvrat,
    texts.BTN_DOKUMENTY: sections.send_dokumenty,
    # BTN_QUESTION — этап 3 (C1).
}


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
        _on_callback(update["callback_query"], bot, cfg)


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

    handler = BUTTONS.get(text.strip())
    if handler:
        handler(bot, chat_id)
        return

    # Поиск по ключевым словам (C3) — этап 3.
    bot.send_message(chat_id, texts.NOT_UNDERSTOOD)


def _on_callback(cq: dict, bot, cfg: Config) -> None:
    # Ответ на нажатие — первым: иначе у клиента крутятся «часики».
    bot.call("answerCallbackQuery", callback_query_id=cq["id"])
    message = cq.get("message")
    if not message or message.get("chat", {}).get("type") != "private":
        return
    chat_id = message["chat"]["id"]
    message_id = message["message_id"]
    data = cq.get("data") or ""

    if data == sections.CB_SOSTAV:
        sections.back_to_sostav(bot, chat_id, message_id)
    elif data.startswith(sections.CB_CARD):
        sections.show_card(bot, chat_id, message_id, data[len(sections.CB_CARD):])
    elif data == sections.CB_NABORY:
        sections.send_nabory(bot, chat_id)
