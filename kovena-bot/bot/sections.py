"""A2, A4, A5, A6 и текстовый дубль наборов (часть E2)."""
from __future__ import annotations

from bot import links, webapp
from bot.context import Ctx
from content import prices, texts

CB_SOSTAV = "sostav"            # список позиций
CB_CARD = "sostav:"             # + ключ позиции
CB_NABORY = "nabory"
CB_PROMO = "promo"


def _inline(*rows: list[dict]) -> dict:
    return {"inline_keyboard": [list(r) for r in rows]}


def _cb(text: str, data: str) -> dict:
    return {"text": text, "callback_data": data}


# ---------------------------------------------------------------- A2

def sostav_list_markup() -> dict:
    return _inline(
        [_cb(title, CB_CARD + key) for key, title in texts.SOSTAV_BUTTONS],
        [links.url_button(texts.BTN_SOSTAV_SITE, links.site("/", "sostav", "sostav"))],
    )


def card_markup() -> dict:
    return _inline([_cb(texts.BTN_NABORY, CB_NABORY), _cb(texts.BTN_BACK, CB_SOSTAV)])


def send_sostav(ctx: Ctx, chat_id: int) -> None:
    ctx.bot.send_message(chat_id, texts.SOSTAV_INTRO, reply_markup=sostav_list_markup())


def show_card(ctx: Ctx, chat_id: int, message_id: int, key: str) -> None:
    text = texts.SOSTAV_CARDS.get(key)
    if text is None:
        return
    ctx.bot.call("editMessageText", chat_id=chat_id, message_id=message_id,
                 text=text, reply_markup=card_markup())


def back_to_sostav(ctx: Ctx, chat_id: int, message_id: int) -> None:
    ctx.bot.call("editMessageText", chat_id=chat_id, message_id=message_id,
                 text=texts.SOSTAV_INTRO, reply_markup=sostav_list_markup())


# ---------------------------------------------------------------- A4, A5, A6

def send_dostavka(ctx: Ctx, chat_id: int) -> None:
    ctx.bot.send_message(chat_id, texts.DOSTAVKA, reply_markup=_inline(
        [links.url_button(texts.BTN_DOSTAVKA_SITE, links.site("/delivery", "dostavka"))]))


def send_vozvrat(ctx: Ctx, chat_id: int) -> None:
    ctx.bot.send_message(chat_id, texts.VOZVRAT, reply_markup=_inline(
        [links.url_button(texts.BTN_OFERTA, links.site("/offer", "vozvrat"))]))


def send_dokumenty(ctx: Ctx, chat_id: int) -> None:
    ctx.bot.send_message(chat_id, texts.DOKUMENTY, reply_markup=_inline(
        [links.url_button(texts.BTN_DOKUMENTY_SITE, links.site("/documents", "dokumenty"))]))


# ---------------------------------------------------------------- Наборы, текст

def nabory_text() -> str:
    parts = [prices.NABORY_INTRO]
    for n in prices.NABORY:
        lines = [f"{n['title']} — {n['price']}", n["subtitle"], n["price_note"]]
        lines += [f"• {item}" for item in n["items"]]
        parts.append("\n".join(lines))
    parts.append(texts.DISCLAIMER)
    return "\n\n".join(parts)


def nabory_markup(ctx: Ctx) -> dict:
    order = webapp.order_button(ctx.cfg, texts.BTN_ORDER, links.site("/", "nabory", "nabory"))
    rows = [[order]]
    if ctx.cfg.promo_code:
        rows.append([_cb(texts.BTN_PROMO, CB_PROMO)])
    return {"inline_keyboard": rows}


def send_nabory(ctx: Ctx, chat_id: int) -> None:
    ctx.bot.send_message(chat_id, nabory_text(), reply_markup=nabory_markup(ctx))
