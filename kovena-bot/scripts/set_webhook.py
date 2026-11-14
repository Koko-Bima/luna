"""Регистрирует вебхук с секретным токеном.

    BOT_TOKEN=... WEBHOOK_SECRET=... python scripts/set_webhook.py https://<id>.apigw.yandexcloud.net/webhook
"""
import os
import sys

import httpx

url = sys.argv[1]
token = os.environ["BOT_TOKEN"]
r = httpx.post(
    f"https://api.telegram.org/bot{token}/setWebhook",
    json={
        "url": url,
        "secret_token": os.environ["WEBHOOK_SECRET"],
        "allowed_updates": ["message", "callback_query"],
        "drop_pending_updates": True,
    },
    timeout=10,
)
print(r.json())
r2 = httpx.get(f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=10)
print(r2.json())
