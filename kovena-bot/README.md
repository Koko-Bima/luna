# kovena-bot

Клиентский Telegram-бот Kovena (`@Kovena_bot`). ТЗ от 14.11.2026. Яндекс Облако, serverless.

## Статус

Код всех функций ТЗ написан, 77 тестов зелёные. **Ничего не развёрнуто.**
Запросы к YDB (`db/ydb_client.py`) не запускались на настоящей базе — тесты идут на `db/memory.py`.
Первое после развёртывания — пройти чек-лист ниже.

| Этап | Что | Код |
|---|---|---|
| 1 | handler, секретный токен, идемпотентность, A1 | готов |
| 2 | тексты с сайта, A2, A4, A5, A6, B1 | готов, ждёт сверки заказчиком |
| 3 | C1–C4: вопрос человеку, часы, ключевые слова, уведомление | готов |
| 4 | YDB, D1, D2, `/stat` | готов |
| 5 | B3, B4, D3, `/status`, `/otzyv` | готов |
| 6 | B2 — за флагом `WEBAPP_ENABLED`; E2 — собран `widget/nabory.html`, **отправка не подключена** | частично |

E2: текстовый дубль уже уходит по кнопке «Наборы и цены». Метод Bot API для отправки HTML-виджета
не сверен с документацией — подключить после проверки (ТЗ разрешает отложить E2).

## Переменные окружения

```
BOT_TOKEN=            # из @BotFather; лучше через Lockbox
WEBHOOK_SECRET=       # 1–256 символов A-Z a-z 0-9 _ -
OPERATOR_CHAT_ID=     # куда приходят вопросы (личка Тани или группа с ботом)
ADMIN_IDS=            # telegram id админов через запятую
WORK_HOURS=10:00-21:00
TZ=Europe/Moscow
YDB_ENDPOINT=grpcs://ydb.serverless.yandexcloud.net:2135
YDB_DATABASE=/ru-central1/...
SITE_URL=https://kovena.ru
PROMO_CODE=TELEGA5
WEBAPP_ENABLED=false  # true — только после ручной проверки оплаты в webview
```

Узнать свой telegram id: написать боту до установки вебхука и открыть
`https://api.telegram.org/bot<TOKEN>/getUpdates` — поле `from.id`. Для группы — `chat.id` (отрицательный).

## Развёртывание

Всё в регионе `ru-central1`. Нужен `yc` CLI, авторизованный на платёжный аккаунт ИП.
В консоли сразу поставить уведомление о расходах на 100 ₽.

```bash
# 1. YDB serverless
yc ydb database create kovena-bot --serverless
yc ydb database get kovena-bot          # endpoint и database
# Схему создать в консоли YDB → «Запросы», вставив db/schema.yql

# 2. Сервисный аккаунт
yc iam service-account create kovena-bot-sa
yc resource-manager folder add-access-binding <FOLDER_ID> --role ydb.editor --service-account-name kovena-bot-sa
yc resource-manager folder add-access-binding <FOLDER_ID> --role functions.functionInvoker --service-account-name kovena-bot-sa

# 3. Функция
yc serverless function create kovena-bot
./deploy/build.sh
yc serverless function version create \
  --function-name kovena-bot --runtime python311 --entrypoint handler.handler \
  --memory 128m --execution-timeout 10s --source-path dist.zip \
  --service-account-id <SA_ID> \
  --environment WEBHOOK_SECRET=...,OPERATOR_CHAT_ID=...,ADMIN_IDS=...,YDB_ENDPOINT=...,YDB_DATABASE=...,PROMO_CODE=TELEGA5 \
  --secret id=<LOCKBOX_ID>,version-id=<VERSION_ID>,key=BOT_TOKEN,environment-variable=BOT_TOKEN

# 4. API Gateway — подставить FUNCTION_ID и SA_ID в deploy/api-gateway.yaml
yc serverless api-gateway create kovena-bot --spec deploy/api-gateway.yaml

# 5. Вебхук
BOT_TOKEN=... WEBHOOK_SECRET=... python scripts/set_webhook.py https://<domain>/webhook
```

## Чек-лист после развёртывания

Инфраструктура и база:
- [ ] `curl -X POST https://<domain>/webhook -d '{}'` → `403`
- [ ] `/start` → приветствие и 6 кнопок; в таблице `users` появилась строка
- [ ] В логах функции на повторную доставку — `duplicate update ... skipped`, второго ответа нет
- [ ] В логах нет текстов сообщений и контактов
- [ ] Счёт за месяц — 0 ₽

Сценарии:
- [ ] Все разделы открываются, ссылки с `utm_source=telegram` и меткой раздела
- [ ] Переход с сайта → оформление → в заявке Tilda видно `utm_campaign`
- [ ] Вопрос доходит оператору с кнопкой «Ответить»; фото и голосовое отклоняются
- [ ] «сколько идёт доставка» → Доставка, «хочу вернуть» → Возврат
- [ ] `/status 1043 отправлен` (админ) → `/zakaz 1043` (клиент) показывает статус и дату
- [ ] `/podpiska` → подписка; `/rassylka` с тестовым текстом → приходит только подписчикам, отписка с первого нажатия
- [ ] `/rassylka` от не-админа — тишина
- [ ] `/status 1043 доставлен`, через 7 дней `/otzyv 1043` — запрос уходит один раз
- [ ] `/stat` показывает цифры

## Тесты и сборка

```bash
pip install -r requirements.txt pytest
python -m pytest -q
python scripts/build_widget.py   # после правки content/prices.py
```

`tests/test_texts_legal.py` проверяет тексты: дисклеймер при упоминании продукта, запрещённые
формулировки, отсутствие ссылок и цен вне `content/`.
