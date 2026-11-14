"""B3. Промокод канала."""
from __future__ import annotations

from bot import links, webapp
from bot.context import Ctx
from content import texts


def send_promo(ctx: Ctx, chat_id: int, tid: int) -> None:
    code = ctx.cfg.promo_code
    if not code:
        ctx.bot.send_message(chat_id, texts.PROMO_NONE)
        return
    url = links.site("/", "promo", "nabory")
    ctx.bot.send_message(chat_id, texts.PROMO.format(code=code), reply_markup={
        "inline_keyboard": [[webapp.order_button(ctx.cfg, texts.BTN_PROMO_ORDER, url)]]})
    ctx.store.mark_promo(tid)
