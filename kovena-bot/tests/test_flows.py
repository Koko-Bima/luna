"""Сценарии этапов 3–6 и пункты приёмки (ТЗ, п. 9)."""
from datetime import datetime, timedelta, timezone

import pytest

from bot import subscribe
from bot.config import Config
from bot.telegram import TelegramError
from content import texts
from handler import process
from tests.conftest import FakeBot
from tests.test_handler import event

ADMIN, CLIENT, OP = 7, 42, -1001
_uid = iter(range(1000, 10**6))


def m(text=None, tid=CLIENT, username="anna", **extra):
    message = {"message_id": 1, "chat": {"id": tid, "type": "private"},
               "from": {"id": tid, **({"username": username} if username else {})}, **extra}
    if text is not None:
        message["text"] = text
    return {"update_id": next(_uid), "message": message}


def cb(data, tid=CLIENT, message_id=5):
    return {"update_id": next(_uid), "callback_query": {
        "id": "x", "data": data, "from": {"id": tid},
        "message": {"message_id": message_id, "chat": {"id": tid, "type": "private"}}}}


@pytest.fixture
def send(cfg, store, bot, clock):
    def _send(update, b=None, c=None):
        r = process(event(update), c or cfg, store, b or bot, now=clock)
        assert r["statusCode"] == 200
    return _send


def texts_to(bot, chat_id):
    return [p["text"] for p in bot.sent_to(chat_id)]


def kb(p):
    return [b for row in (p.get("reply_markup") or {}).get("inline_keyboard", []) for b in row]


# ---------------------------------------------------------------- C1–C4

def test_question_goes_to_operator(send, bot, store):
    send(m(texts.BTN_QUESTION))
    assert texts_to(bot, CLIENT) == [texts.QUESTION_ASK]
    send(m("Когда придёт мой заказ 1043?"))
    [op] = bot.sent_to(OP)
    assert op["text"] == ("❓ Вопрос\nОт: @anna (id 42)\n14.11.2026 12:00\n\n"
                          "Когда придёт мой заказ 1043?")
    assert kb(op) == [{"text": texts.BTN_REPLY, "url": "tg://user?id=42"}]
    assert texts_to(bot, CLIENT)[-1] == texts.QUESTION_SENT
    # Хранится только факт обращения.
    assert store.questions == [(CLIENT, store.now())]
    assert store.get_state(CLIENT) is None


def test_question_photo_and_voice_rejected(send, bot):
    send(m(texts.BTN_QUESTION))
    send(m(photo=[{"file_id": "f"}]))
    send(m(voice={"file_id": "v"}))
    assert texts_to(bot, CLIENT)[1:] == [texts.QUESTION_TEXT_ONLY] * 2
    assert bot.sent_to(OP) == []
    send(m("Теперь текстом"))
    assert len(bot.sent_to(OP)) == 1


def test_off_hours_autoreply_at_3am(send, bot, clock):
    clock.dt = datetime(2026, 11, 14, 0, 0, tzinfo=timezone.utc)  # 03:00 МСК
    send(m(texts.BTN_QUESTION))
    send(m("вопрос ночью"))
    assert texts_to(bot, CLIENT)[-1] == texts.QUESTION_OFF_HOURS
    assert len(bot.sent_to(OP)) == 1  # вопрос всё равно передан


def test_work_hours_edges(send, bot, clock):
    for utc_hour, expected in ((6, texts.QUESTION_OFF_HOURS), (7, texts.QUESTION_SENT),
                               (17, texts.QUESTION_SENT), (18, texts.QUESTION_OFF_HOURS)):
        clock.dt = datetime(2026, 11, 14, utc_hour, 59 if utc_hour in (6, 17) else 0,
                            tzinfo=timezone.utc)
        send(m(texts.BTN_QUESTION))
        send(m("вопрос"))
        assert texts_to(bot, CLIENT)[-1] == expected, utc_hour


def test_hidden_username(send, bot):
    send(m(texts.BTN_QUESTION, username=None))
    send(m("вопрос", username=None))
    [op] = bot.sent_to(OP)
    assert "От: id 42 — username скрыт, ответить можно по кнопке" in op["text"]


def test_privacy_restricted_button_falls_back(send, store, clock, cfg):
    def fail_with_button(params):
        return TelegramError(400, "Bad Request: BUTTON_USER_PRIVACY_RESTRICTED") \
            if params.get("reply_markup") else None
    b = FakeBot(fail_for={OP: fail_with_button})
    send(m(texts.BTN_QUESTION, username=None), b)
    send(m("вопрос", username=None), b)
    [op] = b.sent_to(OP)
    assert op["reply_markup"] is None and "профиль закрыт" in op["text"]
    assert texts_to(b, CLIENT)[-1] == texts.QUESTION_SENT


def test_operator_unreachable_keeps_state(send, store):
    b = FakeBot(fail_for={OP: TelegramError(403, "Forbidden")})
    send(m(texts.BTN_QUESTION), b)
    send(m("вопрос"), b)
    assert texts_to(b, CLIENT)[-1] == texts.QUESTION_FAILED
    assert store.get_state(CLIENT) == "q" and store.questions == []


def test_menu_button_cancels_question(send, bot):
    send(m(texts.BTN_QUESTION))
    send(m(texts.BTN_DOSTAVKA))
    send(m("сколько идёт доставка"))
    assert bot.sent_to(OP) == []
    assert texts_to(bot, CLIENT)[1:] == [texts.DOSTAVKA, texts.DOSTAVKA]


def test_question_state_expires(send, bot, clock):
    send(m(texts.BTN_QUESTION))
    clock.advance(minutes=31)
    send(m("абракадабра"))
    assert bot.sent_to(OP) == []
    assert texts_to(bot, CLIENT)[-1] == texts.NOT_UNDERSTOOD


@pytest.mark.parametrize("phrase,expected", [
    ("сколько идёт доставка", texts.DOSTAVKA),
    ("Сколько идет доставка?", texts.DOSTAVKA),
    ("хочу вернуть", texts.VOZVRAT),
    ("есть сертификаты?", texts.DOKUMENTY),
    ("какой состав", texts.SOSTAV_INTRO),
])
def test_keywords_single(send, bot, phrase, expected):
    send(m(phrase))
    assert texts_to(bot, CLIENT) == [expected]


def test_keyword_promo(send, bot):
    send(m("есть промокод?"))
    assert "TELEGA5" in texts_to(bot, CLIENT)[0]


def test_keywords_multiple_offer_choice(send, bot):
    send(m("сколько стоит доставка"))
    [p] = bot.sent
    assert p["text"] == texts.KEYWORD_CHOICE
    assert [b["callback_data"] for b in kb(p)] == ["sec:dostavka", "sec:nabory"]
    send(cb("sec:dostavka"))
    assert texts_to(bot, CLIENT)[-1] == texts.DOSTAVKA


def test_keywords_none(send, bot):
    send(m("привет"))
    assert texts_to(bot, CLIENT) == [texts.NOT_UNDERSTOOD]


def test_menu_hits_counted(send, store):
    send(m(texts.BTN_DOSTAVKA))
    send(m("хочу вернуть"))
    assert [s for s, _ in store.hits] == ["dostavka", "vozvrat"]


# ---------------------------------------------------------------- B3, B4

def test_promo(send, bot, store):
    send(m("/promo"))
    [p] = bot.sent
    assert p["text"] == texts.PROMO.format(code="TELEGA5")
    [btn] = kb(p)
    assert btn["text"] == texts.BTN_PROMO_ORDER and "utm_campaign=promo" in btn["url"]
    assert store.users[CLIENT]["promo_issued_at"] == store.now()


def test_promo_not_configured(send, bot, cfg):
    send(m("/promo"), c=Config(bot_token="x", webhook_secret="s3cret", promo_code=""))
    assert texts_to(bot, CLIENT) == [texts.PROMO_NONE]


def test_zakaz_found_shows_only_status_and_date(send, bot, store):
    store.set_order_status("1043", "отправлен")
    send(m("/zakaz"))
    send(m("№ 1043"))
    reply = texts_to(bot, CLIENT)[-1]
    assert reply == ("Заказ №1043\nСтатус: отправлен\nОбновлено: 14.11.2026\n\n"
                     "Трек-номер и детали — в письме на вашей почте.")
    assert "₽" not in reply
    assert store.get_order("1043")["telegram_id"] == CLIENT


def test_zakaz_inline_arg_and_not_found(send, bot):
    send(m("/zakaz 9999"))
    assert texts_to(bot, CLIENT) == [texts.ORDER_NOT_FOUND]


def test_zakaz_bad_number_retry(send, bot, store):
    store.set_order_status("1043", "собран")
    send(m("/zakaz"))
    send(m("мой заказ от вторника"))
    send(m("1043"))
    assert texts_to(bot, CLIENT)[1] == texts.ORDER_BAD_NUMBER
    assert "Статус: собран" in texts_to(bot, CLIENT)[2]


# ---------------------------------------------------------------- админ

def test_admin_commands_ignored_for_non_admin(send, bot, store):
    for c in ("/rassylka", "/stat", "/status 1 принят", "/otzyv 1"):
        send(m(c))
    assert bot.calls == [] and store.orders == {}


def test_admin_status(send, bot, store):
    send(m("/status 1043 Отменен", tid=ADMIN))
    assert store.get_order("1043")["status"] == "отменён"
    send(m("/status 1043 потерян", tid=ADMIN))
    assert texts_to(bot, ADMIN)[-1].startswith("Формат")


def test_admin_help(send, bot):
    send(m("/help", tid=ADMIN))
    assert texts_to(bot, ADMIN) == [texts.WELCOME, texts.ADMIN_HELP.format(
        statuses=", ".join(texts.ORDER_STATUSES))]


def test_stat(send, bot, store):
    send(m(texts.BTN_DOSTAVKA))
    send(m("/promo"))
    send(m(texts.BTN_QUESTION))
    send(m("вопрос"))
    send(cb("sub:on"))
    send(m("/stat", tid=ADMIN))
    out = texts_to(bot, ADMIN)[-1]
    assert "За 7 дней: пользователей 2, вопросов 1, выдач промокода 1" in out
    assert "Подписчиков сейчас: 1" in out
    assert "Доставка — 1" in out and "Задать вопрос человеку — 1" in out


# ---------------------------------------------------------------- D1, D2

def test_subscription_default_off_and_toggle(send, bot, store):
    send(m("/start"))
    assert store.is_opted_in(CLIENT) is False
    send(m("/podpiska"))
    assert [b["callback_data"] for b in kb(bot.sent[-1])] == ["sub:on", "sub:no"]
    send(cb("sub:on"))
    assert store.is_opted_in(CLIENT)
    send(m("/podpiska"))
    assert bot.sent[-1]["text"] == texts.SUB_STATUS_ON
    send(cb("unsub"))  # с первого нажатия
    assert store.is_opted_in(CLIENT) is False
    assert texts_to(bot, CLIENT)[-1] == texts.UNSUB_DONE


def test_decline_keeps_off(send, store):
    send(cb("sub:no"))
    assert store.is_opted_in(CLIENT) is False


def _subscribe(store, *ids):
    for t in ids:
        store.set_opt_in(t, True)


def test_broadcast_flow_only_subscribers_with_disclaimer(send, bot, store):
    _subscribe(store, 100, 101)
    store.touch_user(102)  # не подписан
    send(m("/rassylka", tid=ADMIN))
    send(m("Новый набор уже на сайте", tid=ADMIN))
    head, preview, confirm = bot.sent_to(ADMIN)[1:4]
    assert head["text"] == texts.BC_PREVIEW_HEAD
    assert preview["text"] == "Новый набор уже на сайте\n\n" + texts.DISCLAIMER
    assert [b["callback_data"] for b in kb(preview)] == ["unsub"]
    assert confirm["text"] == texts.BC_CONFIRM.format(n=2)
    assert bot.sent_to(100) == []  # до подтверждения — никому

    send(cb("bc:send", tid=ADMIN))
    for t in (100, 101):
        [p] = bot.sent_to(t)
        assert p["text"] == preview["text"] and p["reply_markup"] == preview["reply_markup"]
    assert bot.sent_to(102) == []
    assert texts_to(bot, ADMIN)[-1] == texts.BC_REPORT.format(sent=2, blocked=0, failed=0)
    assert store.get_draft(ADMIN) is None


def test_broadcast_without_product_has_no_disclaimer(send, bot, store):
    _subscribe(store, 100)
    send(m("/rassylka", tid=ADMIN))
    send(m("Мы на каникулах до понедельника", tid=ADMIN))
    send(cb("bc:send", tid=ADMIN))
    assert texts_to(bot, 100) == ["Мы на каникулах до понедельника"]


@pytest.mark.parametrize("word", ["Инозитол", "магния", "омега-3", "₽", "наборов"])
def test_broadcast_disclaimer_markers(word):
    body, _ = subscribe.broadcast_message(f"Новость: {word}")
    assert body.endswith(texts.DISCLAIMER)


def test_broadcast_forbidden_wording_rejected(send, bot, store):
    send(m("/rassylka", tid=ADMIN))
    send(m("Набор повышает шансы на зачатие", tid=ADMIN))
    assert "запрещённые" in texts_to(bot, ADMIN)[-1]
    assert store.get_draft(ADMIN) is None
    assert store.get_state(ADMIN) == "bc"  # можно прислать исправленный


def test_broadcast_blocked_and_errors_reported(send, store, cfg, clock):
    _subscribe(store, 100, 101, 102)
    b = FakeBot(fail_for={101: TelegramError(403, "Forbidden: bot was blocked by the user"),
                          102: TelegramError(400, "Bad Request: chat not found")})
    send(m("/rassylka", tid=ADMIN), b)
    send(m("Привет", tid=ADMIN), b)
    send(cb("bc:send", tid=ADMIN), b)
    assert texts_to(b, ADMIN)[-1] == texts.BC_REPORT.format(sent=1, blocked=1, failed=1)
    assert store.is_opted_in(101) is False  # заблокировавший убран из рассылки


def test_broadcast_cancel(send, bot, store):
    _subscribe(store, 100)
    send(m("/rassylka", tid=ADMIN))
    send(m("Привет", tid=ADMIN))
    send(cb("bc:cancel", tid=ADMIN))
    assert texts_to(bot, ADMIN)[-1] == texts.BC_CANCELLED and bot.sent_to(100) == []


def test_broadcast_callbacks_ignored_for_non_admin(send, bot, store):
    _subscribe(store, 100)
    store.save_draft(ADMIN, "x")
    send(cb("bc:send", tid=CLIENT))
    assert bot.sent == []


def test_broadcast_resumes_after_time_budget(cfg, store, bot, clock):
    from bot.context import Ctx
    _subscribe(store, *range(100, 160))
    store.save_draft(ADMIN, "Привет")
    ctx = Ctx(bot, cfg, store, clock)
    ticks = iter(range(0, 10**6))
    fake_clock = lambda: next(ticks) * 0.1  # noqa: E731 — 0.1 с на каждую проверку времени
    subscribe.run(ctx, ADMIN, ADMIN, clock=fake_clock, sleep=lambda s: None)
    first = len([p for p in bot.sent if p["chat_id"] != ADMIN])
    assert 0 < first < 60
    assert texts_to(bot, ADMIN)[-1].startswith("Отправлена часть")
    subscribe.run(ctx, ADMIN, ADMIN, clock=lambda: 0.0, sleep=lambda s: None)
    delivered = sorted(p["chat_id"] for p in bot.sent if p["chat_id"] != ADMIN)
    assert delivered == list(range(100, 160))  # каждому ровно один раз
    assert texts_to(bot, ADMIN)[-1] == texts.BC_REPORT.format(sent=60, blocked=0, failed=0)


# ---------------------------------------------------------------- D3

def _delivered_order(store, clock, days_ago=8, asker=CLIENT):
    real = clock.dt
    clock.dt = real - timedelta(days=days_ago)
    store.set_order_status("1043", "доставлен")
    if asker:
        store.set_order_asker("1043", asker)
    clock.dt = real


def test_review_once(send, bot, store, clock):
    _delivered_order(store, clock)
    send(m("/otzyv 1043", tid=ADMIN))
    [req] = bot.sent_to(CLIENT)
    assert req["text"] == texts.REVIEW_ASK.format(no="1043")
    assert kb(req) == [{"text": texts.BTN_REVIEW, "callback_data": "review:1043"}]
    send(m("/otzyv 1043", tid=ADMIN))
    assert len(bot.sent_to(CLIENT)) == 1
    assert "уже запрашивали" in texts_to(bot, ADMIN)[-1]


def test_review_reply_goes_to_operator(send, bot, store, clock):
    _delivered_order(store, clock)
    send(m("/otzyv 1043", tid=ADMIN))
    send(cb("review:1043"))
    send(m("Всё пришло быстро"))
    [op] = bot.sent_to(OP)
    assert op["text"].startswith("💬 Отзыв, заказ №1043\n")
    assert texts_to(bot, CLIENT)[-1] == texts.REVIEW_SENT
    assert store.questions == []


def test_review_too_early(send, bot, store, clock):
    _delivered_order(store, clock, days_ago=3)
    send(m("/otzyv 1043", tid=ADMIN))
    assert bot.sent_to(CLIENT) == []
    assert "не раньше чем через 7 дней" in texts_to(bot, ADMIN)[-1]


def test_review_unknown_client_not_sent(send, bot, store, clock):
    _delivered_order(store, clock, asker=None)
    send(m("/otzyv 1043", tid=ADMIN))
    assert texts_to(bot, ADMIN)[-1] == texts.ADMIN_OTZYV_NO_USER.format(no="1043")
    assert store.get_order("1043")["review_asked_at"] is None


def test_review_not_delivered(send, bot, store):
    store.set_order_status("1043", "отправлен")
    store.set_order_asker("1043", CLIENT)
    send(m("/otzyv 1043", tid=ADMIN))
    assert bot.sent_to(CLIENT) == []


# ---------------------------------------------------------------- B2

def test_webapp_flag(send, bot):
    c = Config(bot_token="x", webhook_secret="s3cret", webapp_enabled=True, promo_code="P")
    send(m(texts.BTN_NABORY), c=c)
    order = kb(bot.sent[-1])[0]
    assert "web_app" in order and "utm_campaign=nabory" in order["web_app"]["url"]
    send(m(texts.BTN_NABORY))
    assert "url" in kb(bot.sent[-1])[0]  # по умолчанию — обычная ссылка
