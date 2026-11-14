"""Админ-команды (ТЗ, п. 7). Доступ только у ADMIN_IDS — проверяет роутер."""
from __future__ import annotations

from datetime import timedelta

from bot import orders, subscribe
from bot.context import Ctx
from bot.telegram import TelegramError
from content import texts

COMMANDS = ("status", "otzyv", "rassylka", "stat")
CB_REVIEW = "review:"
REVIEW_DELAY = timedelta(days=7)


def _statuses() -> str:
    return ", ".join(texts.ORDER_STATUSES)


def help_text() -> str:
    return texts.ADMIN_HELP.format(statuses=_statuses())


def dispatch(ctx: Ctx, name: str, arg: str, chat_id: int, admin_id: int) -> None:
    if name == "status":
        cmd_status(ctx, chat_id, arg)
    elif name == "otzyv":
        cmd_otzyv(ctx, chat_id, arg)
    elif name == "rassylka":
        subscribe.start(ctx, chat_id, admin_id)
    elif name == "stat":
        cmd_stat(ctx, chat_id)


def cmd_status(ctx: Ctx, chat_id: int, arg: str) -> None:
    parts = arg.split(maxsplit=1)
    usage = texts.ADMIN_STATUS_USAGE.format(statuses=_statuses())
    if len(parts) != 2:
        ctx.bot.send_message(chat_id, usage)
        return
    no = orders.normalize(parts[0])
    wanted = parts[1].strip().lower().replace("ё", "е")
    status = next((s for s in texts.ORDER_STATUSES if s.replace("ё", "е") == wanted), None)
    if no is None or status is None:
        ctx.bot.send_message(chat_id, usage)
        return
    ctx.store.set_order_status(no, status)
    ctx.bot.send_message(chat_id, texts.ADMIN_STATUS_DONE.format(no=no, status=status))


def cmd_otzyv(ctx: Ctx, chat_id: int, arg: str) -> None:
    no = orders.normalize(arg) if arg else None
    if no is None:
        ctx.bot.send_message(chat_id, texts.ADMIN_OTZYV_USAGE)
        return
    order = ctx.store.get_order(no)
    if order is None:
        ctx.bot.send_message(chat_id, texts.ADMIN_OTZYV_NO_ORDER.format(no=no))
        return
    if order["review_asked_at"]:
        ctx.bot.send_message(chat_id, texts.ADMIN_OTZYV_ALREADY.format(
            no=no, date=ctx.local(order["review_asked_at"]).strftime("%d.%m.%Y")))
        return
    if not order["delivered_at"]:
        ctx.bot.send_message(chat_id, texts.ADMIN_OTZYV_NOT_DELIVERED.format(no=no, status=order["status"]))
        return
    age = ctx.now() - order["delivered_at"]
    if age < REVIEW_DELAY:
        ctx.bot.send_message(chat_id, texts.ADMIN_OTZYV_TOO_EARLY.format(
            days=age.days, date=ctx.local(order["delivered_at"] + REVIEW_DELAY).strftime("%d.%m.%Y")))
        return
    tid = order["telegram_id"]
    if not tid:
        # Искать клиента по другим признакам нельзя (ТЗ, D3).
        ctx.bot.send_message(chat_id, texts.ADMIN_OTZYV_NO_USER.format(no=no))
        return

    markup = {"inline_keyboard": [[{"text": texts.BTN_REVIEW, "callback_data": CB_REVIEW + no}]]}
    try:
        ctx.bot.send_message(tid, texts.REVIEW_ASK.format(no=no), reply_markup=markup)
        reply = texts.ADMIN_OTZYV_SENT
    except TelegramError as e:
        if e.code != 403:
            raise
        reply = texts.ADMIN_OTZYV_BLOCKED
    ctx.store.set_review_asked(no)  # одно сообщение на заказ, даже если не дошло
    ctx.bot.send_message(chat_id, reply.format(no=no))


def cmd_stat(ctx: Ctx, chat_id: int) -> None:
    s7, s30 = ctx.store.stats(7), ctx.store.stats(30)
    sections = "\n".join(f"{texts.SECTION_TITLES.get(k, texts.BTN_QUESTION if k == 'question' else k)} — {n}"
                         for k, n in s30["sections"]) or texts.STAT_NO_SECTIONS
    ctx.bot.send_message(chat_id, texts.STAT.format(
        u7=s7["users"], q7=s7["questions"], p7=s7["promo"],
        u30=s30["users"], q30=s30["questions"], p30=s30["promo"],
        subs=s30["subscribers"], sections=sections))
