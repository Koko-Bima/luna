"""D1 подписка, D2 рассылка."""
from __future__ import annotations

import logging
import time as _time

from bot.context import Ctx
from bot.telegram import TelegramError
from content import legal, texts

log = logging.getLogger("kovena")

CB_SUB_ON, CB_SUB_NO, CB_UNSUB = "sub:on", "sub:no", "unsub"
CB_BC_SEND, CB_BC_CANCEL = "bc:send", "bc:cancel"
STATE_BC = "bc"

BATCH = 25            # получателей за один запрос к базе
PAUSE = 0.05          # ≤ 20 сообщений в секунду, лимит Telegram — 30
TIME_BUDGET = 6.0     # секунд на один вызов функции (таймаут — 10 с)


def _kb(*rows) -> dict:
    return {"inline_keyboard": [list(r) for r in rows]}


def _cb(text: str, data: str) -> dict:
    return {"text": text, "callback_data": data}


# ---------------------------------------------------------------- D1

def cmd_podpiska(ctx: Ctx, chat_id: int, tid: int) -> None:
    if ctx.store.is_opted_in(tid):
        ctx.bot.send_message(chat_id, texts.SUB_STATUS_ON,
                             reply_markup=_kb([_cb(texts.BTN_UNSUB, CB_UNSUB)]))
    else:
        ctx.bot.send_message(chat_id, texts.SUB_ASK, reply_markup=_kb(
            [_cb(texts.BTN_SUB, CB_SUB_ON), _cb(texts.BTN_SUB_NO, CB_SUB_NO)]))


def on_callback(ctx: Ctx, data: str, chat_id: int, message_id: int, tid: int) -> None:
    if data == CB_SUB_ON:
        ctx.store.set_opt_in(tid, True)
        reply = texts.SUB_DONE
    elif data == CB_SUB_NO:
        reply = texts.SUB_DECLINED
    else:  # CB_UNSUB — с первого нажатия, без подтверждения
        ctx.store.set_opt_in(tid, False)
        reply = texts.UNSUB_DONE
    # Убираем кнопки с исходного сообщения, чтобы не жали повторно.
    try:
        ctx.bot.call("editMessageReplyMarkup", chat_id=chat_id, message_id=message_id,
                     reply_markup={"inline_keyboard": []})
    except TelegramError:
        pass
    ctx.bot.send_message(chat_id, reply)


# ---------------------------------------------------------------- D2

def broadcast_message(text: str) -> tuple[str, dict]:
    """Ровно то, что увидит подписчик: текст, дисклеймер при упоминании продукта, кнопка отписки."""
    return legal.with_disclaimer(text.strip()), _kb([_cb(texts.BTN_UNSUB, CB_UNSUB)])


def start(ctx: Ctx, chat_id: int, admin_id: int) -> None:
    ctx.store.set_state(admin_id, STATE_BC)
    ctx.bot.send_message(chat_id, texts.BC_ASK)


def receive_draft(ctx: Ctx, chat_id: int, admin_id: int, text: str | None) -> None:
    if not text:
        ctx.bot.send_message(chat_id, texts.BC_TEXT_ONLY)
        return
    bad = legal.forbidden_words(text)
    if bad:
        ctx.bot.send_message(chat_id, texts.BC_FORBIDDEN.format(words=", ".join(bad)))
        return
    ctx.store.set_state(admin_id, None)
    ctx.store.save_draft(admin_id, text)
    body, markup = broadcast_message(text)
    ctx.bot.send_message(chat_id, texts.BC_PREVIEW_HEAD)
    ctx.bot.send_message(chat_id, body, reply_markup=markup)
    n = ctx.store.count_subscribers()
    ctx.bot.send_message(chat_id, texts.BC_CONFIRM.format(n=n), reply_markup=_kb(
        [_cb(texts.BTN_BC_SEND, CB_BC_SEND), _cb(texts.BTN_BC_CANCEL, CB_BC_CANCEL)]))


def on_admin_callback(ctx: Ctx, data: str, chat_id: int, message_id: int, admin_id: int) -> None:
    # Сразу убираем кнопки — двойное нажатие не запустит две рассылки.
    try:
        ctx.bot.call("editMessageReplyMarkup", chat_id=chat_id, message_id=message_id,
                     reply_markup={"inline_keyboard": []})
    except TelegramError:
        pass
    if data == CB_BC_CANCEL:
        ctx.store.delete_draft(admin_id)
        ctx.bot.send_message(chat_id, texts.BC_CANCELLED)
        return
    run(ctx, chat_id, admin_id)


def run(ctx: Ctx, chat_id: int, admin_id: int, clock=_time.monotonic, sleep=_time.sleep) -> None:
    """Отправляет, пока укладывается в TIME_BUDGET. Прогресс — в базе, продолжение — кнопкой."""
    draft = ctx.store.get_draft(admin_id)
    if draft is None:
        ctx.bot.send_message(chat_id, texts.BC_NO_DRAFT)
        return
    body, markup = broadcast_message(draft["text"])
    last_id, sent, blocked, failed = draft["last_id"], draft["sent"], draft["blocked"], draft["failed"]
    started = clock()
    done = False
    while clock() - started < TIME_BUDGET:
        ids = ctx.store.subscribers_after(last_id, BATCH)
        if not ids:
            done = True
            break
        for tid in ids:
            if clock() - started >= TIME_BUDGET:
                break
            result = _send_one(ctx, tid, body, markup, sleep)
            if result == "sent":
                sent += 1
            elif result == "blocked":
                blocked += 1
                ctx.store.set_opt_in(tid, False)  # заблокировал бота — из рассылки убираем
            else:
                failed += 1
            last_id = tid
            ctx.store.update_draft(admin_id, last_id, sent, blocked, failed)
            sleep(PAUSE)

    if done:
        ctx.store.delete_draft(admin_id)
        ctx.bot.send_message(chat_id, texts.BC_REPORT.format(sent=sent, blocked=blocked, failed=failed))
    else:
        ctx.bot.send_message(chat_id, texts.BC_PARTIAL.format(sent=sent, blocked=blocked, failed=failed),
                             reply_markup=_kb([_cb(texts.BTN_BC_CONTINUE, CB_BC_SEND)]))


def _send_one(ctx: Ctx, tid: int, body: str, markup: dict, sleep) -> str:
    for attempt in range(2):
        try:
            ctx.bot.send_message(tid, body, reply_markup=markup)
            return "sent"
        except TelegramError as e:
            if e.code == 403:
                return "blocked"
            if e.code == 429 and attempt == 0:
                sleep(min(e.retry_after or 1, 3))
                continue
            log.warning("broadcast to user failed: telegram %s", e.code)
            return "failed"
        except Exception as e:  # noqa: BLE001 — сеть; не роняем всю рассылку
            log.warning("broadcast to user failed: %s", type(e).__name__)
            return "failed"
    return "failed"
