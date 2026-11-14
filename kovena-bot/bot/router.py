"""Разбор апдейта и диспетчеризация."""
from __future__ import annotations

from bot import admin, menu, orders, promo, sections, subscribe, support
from bot.context import Ctx
from content import texts

CB_SECTION = "sec:"   # выбор раздела после поиска по словам

# Раздел → (ctx, chat_id, tid)
SECTIONS = {
    "nabory": lambda ctx, chat, tid: sections.send_nabory(ctx, chat),
    "sostav": lambda ctx, chat, tid: sections.send_sostav(ctx, chat),
    "dostavka": lambda ctx, chat, tid: sections.send_dostavka(ctx, chat),
    "vozvrat": lambda ctx, chat, tid: sections.send_vozvrat(ctx, chat),
    "dokumenty": lambda ctx, chat, tid: sections.send_dokumenty(ctx, chat),
    "promo": promo.send_promo,
    "question": support.ask,
}

BUTTONS = {
    texts.BTN_NABORY: "nabory",
    texts.BTN_SOSTAV: "sostav",
    texts.BTN_DOSTAVKA: "dostavka",
    texts.BTN_VOZVRAT: "vozvrat",
    texts.BTN_DOKUMENTY: "dokumenty",
    texts.BTN_QUESTION: "question",
}


def parse_command(text: str) -> tuple[str, str] | None:
    """'/start@kovena_bot payload' -> ('start', 'payload')."""
    if not text.startswith("/"):
        return None
    head, _, rest = text.partition(" ")
    name = head[1:].split("@", 1)[0].lower()
    return name, rest.strip()


def open_section(ctx: Ctx, key: str, chat_id: int, tid: int) -> None:
    ctx.store.add_hit(key)
    SECTIONS[key](ctx, chat_id, tid)


def handle_update(update: dict, ctx: Ctx) -> None:
    if "message" in update:
        _on_message(update["message"], ctx)
    elif "callback_query" in update:
        _on_callback(update["callback_query"], ctx)


# ---------------------------------------------------------------- сообщения

def _on_message(msg: dict, ctx: Ctx) -> None:
    chat = msg.get("chat", {})
    # Работаем только в личке. Чат оператора и любые группы — не наше дело.
    if chat.get("type") != "private":
        return
    chat_id = chat["id"]
    tid = (msg.get("from") or {}).get("id", chat_id)
    text = msg.get("text")
    is_admin = ctx.is_admin(tid)

    cmd = parse_command(text) if text else None
    if cmd and cmd[0] in admin.COMMANDS:
        if is_admin:
            ctx.store.touch_user(tid)
            ctx.store.set_state(tid, None)
            admin.dispatch(ctx, cmd[0], cmd[1], chat_id, tid)
        return  # не-админу — молча ничего

    ctx.store.touch_user(tid)
    state = ctx.store.get_state(tid)

    def reset():
        if state:
            ctx.store.set_state(tid, None)

    if cmd:
        reset()
        _on_command(ctx, cmd, chat_id, tid, is_admin)
        return

    if text and text.strip() in BUTTONS:
        reset()
        open_section(ctx, BUTTONS[text.strip()], chat_id, tid)
        return

    if state:
        if state == support.STATE_QUESTION or state.startswith(support.STATE_REVIEW):
            support.submit(ctx, msg, state)
        elif state == orders.STATE:
            if text:
                orders.lookup(ctx, chat_id, tid, text)
            else:
                ctx.bot.send_message(chat_id, texts.ORDER_BAD_NUMBER)
        elif state == subscribe.STATE_BC and is_admin:
            subscribe.receive_draft(ctx, chat_id, tid, text)
        else:
            reset()
            ctx.bot.send_message(chat_id, texts.NOT_UNDERSTOOD)
        return

    if not text:
        ctx.bot.send_message(chat_id, texts.NOT_UNDERSTOOD)
        return

    # C3 — только словарь, никакой генерации.
    found = support.match_sections(text)
    if len(found) == 1:
        open_section(ctx, found[0], chat_id, tid)
    elif found:
        ctx.bot.send_message(chat_id, texts.KEYWORD_CHOICE, reply_markup={"inline_keyboard": [
            [{"text": texts.SECTION_TITLES[k], "callback_data": CB_SECTION + k}] for k in found]})
    else:
        ctx.bot.send_message(chat_id, texts.NOT_UNDERSTOOD)


def _on_command(ctx: Ctx, cmd: tuple[str, str], chat_id: int, tid: int, is_admin: bool) -> None:
    name, arg = cmd
    if name in ("start", "menu"):
        menu.send_menu(ctx.bot, chat_id)
    elif name == "help":
        menu.send_menu(ctx.bot, chat_id)
        if is_admin:
            ctx.bot.send_message(chat_id, admin.help_text())
    elif name == "zakaz":
        if arg:
            orders.lookup(ctx, chat_id, tid, arg)
        else:
            orders.ask(ctx, chat_id, tid)
    elif name == "promo":
        open_section(ctx, "promo", chat_id, tid)
    elif name == "podpiska":
        subscribe.cmd_podpiska(ctx, chat_id, tid)
    else:
        ctx.bot.send_message(chat_id, texts.NOT_UNDERSTOOD)


# ---------------------------------------------------------------- кнопки под сообщениями

def _on_callback(cq: dict, ctx: Ctx) -> None:
    # Ответ на нажатие — первым: иначе у клиента крутятся «часики».
    ctx.bot.call("answerCallbackQuery", callback_query_id=cq["id"])
    message = cq.get("message")
    if not message or message.get("chat", {}).get("type") != "private":
        return
    chat_id = message["chat"]["id"]
    message_id = message["message_id"]
    tid = (cq.get("from") or {}).get("id", chat_id)
    data = cq.get("data") or ""

    if data.startswith("bc:"):
        if ctx.is_admin(tid):
            subscribe.on_admin_callback(ctx, data, chat_id, message_id, tid)
        return

    ctx.store.touch_user(tid)
    if data == sections.CB_SOSTAV:
        sections.back_to_sostav(ctx, chat_id, message_id)
    elif data.startswith(sections.CB_CARD):
        sections.show_card(ctx, chat_id, message_id, data[len(sections.CB_CARD):])
    elif data == sections.CB_NABORY:
        open_section(ctx, "nabory", chat_id, tid)
    elif data == sections.CB_PROMO:
        open_section(ctx, "promo", chat_id, tid)
    elif data.startswith(CB_SECTION):
        key = data[len(CB_SECTION):]
        if key in SECTIONS:
            open_section(ctx, key, chat_id, tid)
    elif data in (subscribe.CB_SUB_ON, subscribe.CB_SUB_NO, subscribe.CB_UNSUB):
        subscribe.on_callback(ctx, data, chat_id, message_id, tid)
    elif data.startswith(admin.CB_REVIEW):
        no = orders.normalize(data[len(admin.CB_REVIEW):])
        if no:
            support.ask_review(ctx, chat_id, tid, no)
