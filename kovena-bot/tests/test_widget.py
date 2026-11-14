"""E2 — рамки платформы (ТЗ, п. 6)."""
import re
import sys
from pathlib import Path

from content import prices, texts

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_widget  # noqa: E402


def test_built_file_is_fresh():
    """widget/nabory.html пересобран после правки цен: python scripts/build_widget.py"""
    assert build_widget.OUT.read_text(encoding="utf-8") == build_widget.build()


def test_size_limit():
    assert len(build_widget.build().encode("utf-8")) <= 32 * 1024


def test_no_network_inputs_images():
    html = build_widget.build().lower()
    assert not re.search(r"https?://|src=|<link|@import|url\(", html)
    for tag in ("<input", "<textarea", "<select", "<img", "<video", "<iframe", "webgl", "fetch(",
                "xmlhttprequest"):
        assert tag not in html, tag


def test_contains_prices_and_disclaimer():
    html = build_widget.build()
    assert texts.DISCLAIMER in html
    for n in prices.NABORY:
        assert n["price"] in html and n["subtitle"] in html
