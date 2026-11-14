"""Правовой контур (ТЗ, п. 2.3, 9): проверяется на каждом прогоне тестов."""
import re

from content import texts

PRODUCT_MARKERS = ("бад", "набор", "инозитол", "магний", "омега", "₽", "состав")
FORBIDDEN = ("зачат", "фертильн", "беремен", "дефицит", "помогает",
             "повышает шансы", "восполняет", "забеременеть")


def all_strings():
    for name, value in vars(texts).items():
        if name.startswith("_") or name == "DISCLAIMER":
            continue
        if isinstance(value, str):
            yield name, value


def test_product_mentions_have_disclaimer():
    for name, s in all_strings():
        if name.startswith("BTN_"):
            continue  # подпись кнопки — не сообщение
        if any(m in s.lower() for m in PRODUCT_MARKERS):
            assert texts.DISCLAIMER in s, f"{name}: нет дисклеймера"


def test_no_forbidden_wording():
    for name, s in all_strings():
        low = s.lower()
        for w in FORBIDDEN:
            assert w not in low, f"{name}: запрещённое «{w}»"


def test_no_hardcoded_links():
    for name, s in all_strings():
        assert not re.search(r"https?://|kovena\.ru", s), f"{name}: ссылка — только через links.site()"
