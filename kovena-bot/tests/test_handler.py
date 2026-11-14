import base64
import json

from bot.telegram import TelegramError
from content import texts
from handler import process
from tests.conftest import FakeBot


def event(update, secret="s3cret", b64=False, header="X-Telegram-Bot-Api-Secret-Token"):
    body = json.dumps(update)
    if b64:
        body = base64.b64encode(body.encode()).decode()
    headers = {header: secret} if secret is not None else {}
    return {"httpMethod": "POST", "headers": headers, "body": body, "isBase64Encoded": b64}


def msg(text, update_id=1, chat_type="private"):
    return {
        "update_id": update_id,
        "message": {"message_id": 1, "chat": {"id": 42, "type": chat_type},
                    "from": {"id": 42}, "text": text},
    }


def test_no_secret_403(cfg, store, bot):
    assert process(event(msg("/start"), secret=None), cfg, store, bot)["statusCode"] == 403
    assert bot.calls == [] and store.seen == set()


def test_wrong_secret_403(cfg, store, bot):
    assert process(event(msg("/start"), secret="nope"), cfg, store, bot)["statusCode"] == 403


def test_empty_configured_secret_rejects_everything(store, bot):
    from bot.config import Config
    c = Config(bot_token="x", webhook_secret="")
    assert process(event(msg("/start"), secret=""), c, store, bot)["statusCode"] == 403


def test_lowercase_header_accepted(cfg, store, bot):
    ev = event(msg("/start"), header="x-telegram-bot-api-secret-token")
    assert process(ev, cfg, store, bot)["statusCode"] == 200


def test_start_sends_menu(cfg, store, bot):
    r = process(event(msg("/start")), cfg, store, bot)
    assert r["statusCode"] == 200
    [m] = bot.sent
    assert m["text"] == texts.WELCOME
    rows = [[b["text"] for b in row] for row in m["reply_markup"]["keyboard"]]
    assert rows == texts.MAIN_KEYBOARD
    assert m["reply_markup"]["is_persistent"]


def test_menu_and_start_with_payload(cfg, store, bot):
    process(event(msg("/menu", 1)), cfg, store, bot)
    process(event(msg("/start@kovena_bot ref", 2)), cfg, store, bot)
    assert [m["text"] for m in bot.sent] == [texts.WELCOME, texts.WELCOME]


def test_base64_body(cfg, store, bot):
    assert process(event(msg("/start"), b64=True), cfg, store, bot)["statusCode"] == 200
    assert len(bot.sent) == 1


def test_duplicate_update_processed_once(cfg, store, bot):
    for _ in range(3):
        assert process(event(msg("/start", 7)), cfg, store, bot)["statusCode"] == 200
    assert len(bot.sent) == 1


def test_crash_unmarks_for_retry(cfg, store):
    broken = FakeBot(fail=RuntimeError("boom"))
    assert process(event(msg("/start", 9)), cfg, store, broken)["statusCode"] == 500
    assert 9 not in store.seen
    ok = FakeBot()
    assert process(event(msg("/start", 9)), cfg, store, ok)["statusCode"] == 200
    assert len(ok.sent) == 1


def test_blocked_by_user_is_final(cfg, store):
    blocked = FakeBot(fail=TelegramError(403, "Forbidden: bot was blocked by the user"))
    assert process(event(msg("/start", 10)), cfg, store, blocked)["statusCode"] == 200
    assert 10 in store.seen


def test_group_chat_ignored(cfg, store, bot):
    process(event(msg("/start", chat_type="supergroup")), cfg, store, bot)
    assert bot.calls == []


def test_unknown_text_and_media(cfg, store, bot):
    process(event(msg("абракадабра", 1)), cfg, store, bot)
    photo = {"update_id": 2, "message": {"chat": {"id": 42, "type": "private"}, "photo": []}}
    process(event(photo), cfg, store, bot)
    assert [m["text"] for m in bot.sent] == [texts.NOT_UNDERSTOOD] * 2


def test_garbage_body_400(cfg, store, bot):
    ev = {"headers": {"X-Telegram-Bot-Api-Secret-Token": "s3cret"}, "body": "not json"}
    assert process(ev, cfg, store, bot)["statusCode"] == 400


def test_logs_do_not_contain_message_text(cfg, store, caplog):
    secret_text = "мой телефон +79990000000"
    broken = FakeBot(fail=RuntimeError(secret_text))
    with caplog.at_level("INFO"):
        process(event(msg(secret_text, 11)), cfg, store, broken)
        process(event(msg(secret_text, 12)), cfg, store, FakeBot())
        process(event(msg(secret_text, 12)), cfg, store, FakeBot())
    assert "+7999" not in caplog.text and "телефон" not in caplog.text
