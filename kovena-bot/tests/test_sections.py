from urllib.parse import parse_qs, urlparse

from bot import sections
from content import texts
from handler import process
from tests.test_handler import event, msg


def cb(data, update_id=100, message_id=55):
    return {"update_id": update_id, "callback_query": {
        "id": "cbid", "data": data, "from": {"id": 42},
        "message": {"message_id": message_id, "chat": {"id": 42, "type": "private"}}}}


def buttons(markup):
    return [b for row in markup["inline_keyboard"] for b in row]


def utm(url):
    q = parse_qs(urlparse(url).query)
    return q["utm_source"][0], q["utm_medium"][0], q["utm_campaign"][0]


def run(update, cfg, store, bot):
    assert process(event(update), cfg, store, bot)["statusCode"] == 200


def test_menu_buttons_open_sections(cfg, store, bot):
    expected = {
        texts.BTN_SOSTAV: (texts.SOSTAV_INTRO, "sostav"),
        texts.BTN_DOSTAVKA: (texts.DOSTAVKA, "dostavka"),
        texts.BTN_VOZVRAT: (texts.VOZVRAT, "vozvrat"),
        texts.BTN_DOKUMENTY: (texts.DOKUMENTY, "dokumenty"),
        texts.BTN_NABORY: (sections.nabory_text(), "nabory"),
    }
    for i, (btn, (text, campaign)) in enumerate(expected.items()):
        bot.calls.clear()
        run(msg(btn, update_id=i + 1), cfg, store, bot)
        [m] = bot.sent
        assert m["text"] == text
        urls = [b["url"] for b in buttons(m["reply_markup"]) if "url" in b]
        assert urls, btn
        for u in urls:
            assert u.startswith("https://kovena.ru")
            assert utm(u) == ("telegram", "bot", campaign)


def test_section_paths(cfg, store, bot):
    paths = {}
    for i, btn in enumerate([texts.BTN_DOSTAVKA, texts.BTN_VOZVRAT, texts.BTN_DOKUMENTY]):
        bot.calls.clear()
        run(msg(btn, update_id=i + 1), cfg, store, bot)
        paths[btn] = urlparse(buttons(bot.sent[0]["reply_markup"])[0]["url"]).path
    assert paths == {texts.BTN_DOSTAVKA: "/delivery", texts.BTN_VOZVRAT: "/offer",
                     texts.BTN_DOKUMENTY: "/documents"}


def test_sostav_has_three_cards(cfg, store, bot):
    run(msg(texts.BTN_SOSTAV), cfg, store, bot)
    cbs = [b["text"] for b in buttons(bot.sent[0]["reply_markup"]) if "callback_data" in b]
    assert cbs == ["Инозитол", "Магний + В6", "Омега-3"]


def test_card_edit_and_back(cfg, store, bot):
    run(cb("sostav:magniy", 1), cfg, store, bot)
    run(cb("sostav", 2), cfg, store, bot)
    methods = [m for m, _ in bot.calls]
    assert methods == ["answerCallbackQuery", "editMessageText"] * 2
    card, back = [p for m, p in bot.calls if m == "editMessageText"]
    assert card["text"] == texts.SOSTAV_CARDS["magniy"] and card["message_id"] == 55
    assert [b["text"] for b in buttons(card["reply_markup"])] == [texts.BTN_NABORY, texts.BTN_BACK]
    assert back["text"] == texts.SOSTAV_INTRO


def test_card_nabory_button_sends_prices(cfg, store, bot):
    run(cb("nabory"), cfg, store, bot)
    [m] = bot.sent
    assert "2 990 ₽" in m["text"] and "5 900 ₽" in m["text"]
    assert m["text"].endswith(texts.DISCLAIMER)
    assert [b["text"] for b in buttons(m["reply_markup"])] == [texts.BTN_ORDER, texts.BTN_PROMO]


def test_unknown_callback_only_answered(cfg, store, bot):
    run(cb("sostav:nope", 1), cfg, store, bot)
    run(cb("garbage", 2), cfg, store, bot)
    assert [m for m, _ in bot.calls] == ["answerCallbackQuery"] * 2


def test_links_reject_unknown_campaign():
    import pytest
    from bot import links
    with pytest.raises(ValueError):
        links.site("/", "typo")
    assert links.site("/", "nabory", "nabory") == \
        "https://kovena.ru/?utm_source=telegram&utm_medium=bot&utm_campaign=nabory#nabory"
