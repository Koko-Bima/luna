"""Правовой контур (ТЗ, п. 2.3, 9): проверяется на каждом прогоне тестов."""
import re

from bot import sections
from content import legal, prices, texts

# Служебные тексты для админа и оператора — не реклама.
SERVICE_PREFIXES = ("_", "BTN_", "ADMIN_", "BC_", "OP_", "STAT")


def messages():
    """Все тексты, которые бот отправляет как сообщения."""
    for name, value in vars(texts).items():
        if name.startswith(SERVICE_PREFIXES) or name == "DISCLAIMER":
            continue
        if isinstance(value, str):
            yield name, value
    for key, card in texts.SOSTAV_CARDS.items():
        yield f"SOSTAV_CARDS[{key}]", card
    yield "nabory_text()", sections.nabory_text()


def test_product_mentions_have_disclaimer():
    for name, s in messages():
        if legal.mentions_product(s):
            assert texts.DISCLAIMER in s, f"{name}: нет дисклеймера"


def test_no_forbidden_wording():
    for name, s in messages():
        assert not legal.forbidden_words(s), f"{name}: {legal.forbidden_words(s)}"


def test_no_hardcoded_links():
    for name, s in messages():
        assert not re.search(r"https?://|(?<!@)kovena\.ru", s), \
            f"{name}: ссылка — только через links.site()"


def test_prices_not_outside_content():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    for f in list((root / "bot").glob("*.py")) + [root / "handler.py"]:
        src = f.read_text(encoding="utf-8")
        for p in (n["price"] for n in prices.NABORY):
            assert p not in src, f"{f.name}: цена вне content/"
        assert "kovena.ru" not in src.replace('"https://kovena.ru"', ""), f"{f.name}: ссылка"


def test_sgr_numbers_are_latin():
    for m in re.findall(r"\S+\.R\.\d{6}\.\d\d\.\d\d", texts.DOKUMENTY):
        assert m.isascii(), f"кириллица в номере СГР: {m}"
