"""A1. Приветствие и постоянное меню."""
from __future__ import annotations

from content import texts


def main_keyboard() -> dict:
    return {
        "keyboard": [[{"text": t} for t in row] for row in texts.MAIN_KEYBOARD],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def send_menu(bot, chat_id: int) -> None:
    bot.send_message(chat_id, texts.WELCOME, reply_markup=main_keyboard())
