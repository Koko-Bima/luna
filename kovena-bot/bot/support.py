"""C1 вопрос человеку, C2 рабочие часы, C3 поиск по ключевым словам, C4 уведомление оператору."""
from __future__ import annotations

import logging
from datetime import time

from bot.context import Ctx
from bot.telegram import TelegramError
from content import texts
from content.keywords import KEYWORDS

log = logging.getLogger("kovena")

STATE_QUESTION = "q"
STATE_REVIEW = "r:"          # + номер заказа
MAX_FORWARD = 3500           # лимит сообщения Telegram — 4096 вместе с шапкой


# ---------------------------------------------------------------- C2

def _parse_hours(raw: str) -> tuple[time, time]:
    start, end = raw.replace(" ", "").split("-")
    return time.fromisoformat(start), time.fromisoformat(end)


def is_work_time(ctx: Ctx) -> bool:
    start, end = _parse_hours(ctx.cfg.work_hours)
    now = ctx.local().time()
    return start <= now < end


# ---------------------------------------------------------------- C1

def ask(ctx: Ctx, chat_id: int, tid: int) -> None:
    ctx.store.set_state(tid, STATE_QUESTION)
    ctx.bot.send_message(chat_id, texts.QUESTION_ASK)


def ask_review(ctx: Ctx, chat_id: int, tid: int, order_no: str) -> None:
    ctx.store.set_state(tid, STATE_REVIEW + order_no)
    ctx.bot.send_message(chat_id, texts.REVIEW_PROMPT)


def submit(ctx: Ctx, msg: dict, state: str) -> None:
    """Пришло сообщение в состоянии «ждём вопрос/отзыв»."""
    chat_id = msg["chat"]["id"]
    user = msg.get("from") or {}
    tid = user.get("id", chat_id)
    text = msg.get("text")
    if not text:
        # Фото, голосовые, видео, файлы — отклоняются. Состояние сохраняем.
        ctx.bot.send_message(chat_id, texts.QUESTION_TEXT_ONLY)
        return

    review_no = state[len(STATE_REVIEW):] if state.startswith(STATE_REVIEW) else None
    head = texts.OP_REVIEW_HEAD.format(no=review_no) if review_no else texts.OP_QUESTION_HEAD

    if not notify_operator(ctx, user, head, text):
        ctx.bot.send_message(chat_id, texts.QUESTION_FAILED)
        return  # состояние не сбрасываем — клиент может отправить ещё раз

    ctx.store.set_state(tid, None)
    if review_no:
        ctx.bot.send_message(chat_id, texts.REVIEW_SENT)
        return
    ctx.store.add_question(tid)  # только факт обращения, без текста
    ctx.bot.send_message(chat_id, texts.QUESTION_SENT if is_work_time(ctx) else texts.QUESTION_OFF_HOURS)


# ---------------------------------------------------------------- C4

def notify_operator(ctx: Ctx, user: dict, head: str, text: str) -> bool:
    op = ctx.cfg.operator_chat_id
    if op is None:
        log.error("OPERATOR_CHAT_ID is not set")
        return False
    uid = user.get("id")
    username = user.get("username")
    when = ctx.local().strftime("%d.%m.%Y %H:%M")
    body = text if len(text) <= MAX_FORWARD else text[:MAX_FORWARD] + "…"

    def compose(from_line: str) -> str:
        return f"{head}\n{from_line}\n{when}\n\n{body}"

    from_line = (texts.OP_FROM_USERNAME.format(username=username, id=uid) if username
                 else texts.OP_FROM_HIDDEN.format(id=uid))
    button = {"inline_keyboard": [[{"text": texts.BTN_REPLY, "url": f"tg://user?id={uid}"}]]}
    try:
        ctx.bot.send_message(op, compose(from_line), reply_markup=button)
        return True
    except TelegramError as e:
        if e.code != 400:
            log.error("operator notify failed: telegram %s", e.code)
            return False
        # Настройки приватности клиента запрещают ссылку на профиль — шлём без кнопки.
    try:
        line = from_line if username else texts.OP_FROM_NO_BUTTON.format(id=uid)
        ctx.bot.send_message(op, compose(line))
        return True
    except TelegramError as e:
        log.error("operator notify failed: telegram %s", e.code)
        return False


# ---------------------------------------------------------------- C3

def _norm(s: str) -> str:
    return s.lower().replace("ё", "е")


def match_sections(text: str) -> list[str]:
    """Разделы, чьи ключевые слова есть в тексте.

    Совпадение, целиком лежащее внутри более длинного совпадения другого
    раздела, не считается: «сколько идёт доставка» — это доставка, а не
    «сколько» из раздела цен.
    """
    low = _norm(text)
    spans: list[tuple[int, int, str]] = []
    for section, words in KEYWORDS.items():
        for w in words:
            w = _norm(w)
            start = low.find(w)
            while start != -1:
                spans.append((start, start + len(w), section))
                start = low.find(w, start + 1)
    kept = []
    for s, e, sec in spans:
        covered = any(s2 <= s and e <= e2 and (e2 - s2) > (e - s) and sec2 != sec
                      for s2, e2, sec2 in spans)
        if not covered:
            kept.append(sec)
    # Порядок словаря, без повторов.
    return [sec for sec in KEYWORDS if sec in kept]
