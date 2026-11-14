# kovena-bot

Клиентский Telegram-бот Kovena. ТЗ от 14.11.2026. Яндекс Облако, serverless.

## Статус по этапам (ТЗ, п. 8)

| Этап | Что | Статус |
|---|---|---|
| 1 | handler, роутер, секретный токен, идемпотентность, A1 | код готов, тесты зелёные, **ждёт развёртывания и проверки** |
| 2 | texts.py, A2, A4, A5, A6, B1 | ждёт текстов с сайта |
| 3–6 | остальное | не начато |

## Развёртывание этапа 1

Всё в регионе `ru-central1`. Нужен `yc` CLI, авторизованный на платёжный аккаунт ИП.

```bash
# 1. YDB serverless
yc ydb database create kovena-bot --serverless
yc ydb database get kovena-bot   # запомнить endpoint и database
# Схему создать в консоли YDB → «Запросы», вставив db/schema.yql

# 2. Сервисный аккаунт для функции и шлюза
yc iam service-account create kovena-bot-sa
yc resource-manager folder add-access-binding <FOLDER_ID> \
  --role ydb.editor --service-account-name kovena-bot-sa
yc resource-manager folder add-access-binding <FOLDER_ID> \
  --role functions.functionInvoker --service-account-name kovena-bot-sa

# 3. Функция
yc serverless function create kovena-bot
./deploy/build.sh
yc serverless function version create \
  --function-name kovena-bot --runtime python311 --entrypoint handler.handler \
  --memory 128m --execution-timeout 10s --source-path dist.zip \
  --service-account-id <SA_ID> \
  --environment BOT_TOKEN=...,WEBHOOK_SECRET=...,YDB_ENDPOINT=grpcs://ydb.serverless.yandexcloud.net:2135,YDB_DATABASE=/ru-central1/...,WORK_HOURS=10:00-21:00,SITE_URL=https://kovena.ru

# 4. API Gateway — подставить FUNCTION_ID и SA_ID в deploy/api-gateway.yaml
yc serverless api-gateway create kovena-bot --spec deploy/api-gateway.yaml

# 5. Вебхук
BOT_TOKEN=... WEBHOOK_SECRET=... python scripts/set_webhook.py https://<domain>/webhook
```

`WEBHOOK_SECRET` — 1–256 символов `A-Z a-z 0-9 _ -`, например `python -c "import secrets;print(secrets.token_urlsafe(32))"`.
Токен бота лучше хранить в Lockbox, а не открытой переменной.

## Проверка этапа 1

- [ ] `/start` и `/menu` → приветствие и клавиатура из 6 кнопок
- [ ] `curl -X POST https://<domain>/webhook -d '{}'` → `403`
- [ ] В логах функции на повторную доставку — `duplicate update ... skipped`, второго ответа нет
- [ ] В логах нет текстов сообщений

## Тесты

```bash
pip install -r requirements.txt pytest
python -m pytest -q
```

`tests/test_texts_legal.py` проверяет `content/texts.py`: дисклеймер при упоминании продукта, отсутствие запрещённых формулировок и ссылок.
