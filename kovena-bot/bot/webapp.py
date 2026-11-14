"""B2. Кнопка заказа: web_app (сайт внутри Telegram) или обычная ссылка.

WEBAPP_ENABLED=true включать только после ручной проверки оплаты Точки в webview.
"""
from __future__ import annotations

from bot.config import Config


def order_button(cfg: Config, text: str, url: str) -> dict:
    if cfg.webapp_enabled:
        return {"text": text, "web_app": {"url": url}}
    return {"text": text, "url": url}
