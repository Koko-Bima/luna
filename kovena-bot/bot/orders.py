"""B4. Статус заказа по номеру. Показываются только статус и дата."""
from __future__ import annotations

import re

from bot.context import Ctx
from content import texts

STATE = "o"
_VALID = re.compile(r"^[0-9A-Za-z-]{1,32}$")


def normalize(raw: str) -> str | None:
    no = raw.strip().lstrip("№#Nn").strip().replace(" ", "")
    return no if _VALID.match(no) else None


def ask(ctx: Ctx, chat_id: int, tid: int) -> None:
    ctx.store.set_state(tid, STATE)
    ctx.bot.send_message(chat_id, texts.ORDER_ASK)


def lookup(ctx: Ctx, chat_id: int, tid: int, raw: str) -> None:
    no = normalize(raw)
    if no is None:
        ctx.store.set_state(tid, STATE)  # даём ещё попытку
        ctx.bot.send_message(chat_id, texts.ORDER_BAD_NUMBER)
        return
    ctx.store.set_state(tid, None)
    order = ctx.store.get_order(no)
    if order is None:
        ctx.bot.send_message(chat_id, texts.ORDER_NOT_FOUND)
        return
    ctx.store.set_order_asker(no, tid)  # для D3
    ctx.bot.send_message(chat_id, texts.ORDER_FOUND.format(
        no=no, status=order["status"], date=ctx.local(order["updated_at"]).strftime("%d.%m.%Y")))
