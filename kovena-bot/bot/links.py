"""B1. Все ссылки на сайт — только отсюда, с UTM-меткой раздела."""
from __future__ import annotations

import os
from urllib.parse import urlencode

CAMPAIGNS = {"nabory", "sostav", "dostavka", "vozvrat", "dokumenty", "promo"}


def site(path: str, campaign: str, anchor: str | None = None) -> str:
    if campaign not in CAMPAIGNS:
        raise ValueError(f"unknown campaign {campaign!r}")
    base = os.environ.get("SITE_URL", "https://kovena.ru").rstrip("/")
    query = urlencode({"utm_source": "telegram", "utm_medium": "bot", "utm_campaign": campaign})
    url = f"{base}{path}?{query}"
    return f"{url}#{anchor}" if anchor else url


def url_button(text: str, url: str) -> dict:
    return {"text": text, "url": url}
