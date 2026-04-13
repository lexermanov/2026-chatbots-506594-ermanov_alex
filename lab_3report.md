University: [ITMO University](https://itmo.ru/ru/)

Faculty: [FTMI]

Course: [Vibe Coding: AI-боты для бизнеса](https://github.com/itmo-ict-faculty/vibe-coding-for-business)

Year: 2025/2026

Group: U4125

Author: Ermanov Alexey 506594

Lab: Lab3

Date of create: 13.04.2026
Date of finished: -

## Описание деплоя

Для деплоя выбран `Railway` с подключением GitHub-репозитория и запуском Telegram-бота в режиме `webhook`.

Выбранный способ:
- Деплой из GitHub (`Deploy from GitHub repo`) в Railway.
- Публичный домен Railway для приема webhook от Telegram.

Почему выбран именно этот способ:
- Быстрый старт без ручной настройки серверов и Docker.
- Удобная работа с переменными окружения (`BOT_TOKEN`, `WEBHOOK_URL`) через интерфейс Railway.
- Подходит для Telegram webhook-сценария в учебной задаче.

## URL бота

https://t.me/itmoftmi_aes_bot

@itmoftmi_aes_bot

## Процесс деплоя

### Пошаговая инструкция

1. Подготовка проекта:
   - Добавлен `.gitignore` (`.env`, `*.pyc`, `__pycache__/`, `*.db`, `*.log`).
   - Обновлен `requirements.txt` с фиксированными версиями библиотек.
   - Настроено логирование в `bot.py`.
2. Публикация проекта в GitHub:
   - Создан репозиторий `2026-chatbots-506594-ermanov_alex`.
   - Выполнены `git init`, `git add`, `git commit`, `git push`.
3. Подключение к Railway:
   - Создан проект в Railway через `Deploy from GitHub repo`.
   - Настроены переменные окружения (`BOT_TOKEN`/`TELEGRAM_BOT_TOKEN`, `WEBHOOK_URL`).
4. Настройка Python-окружения для сборки:
   - Добавлены `.python-version` и `nixpacks.toml` для фикса версии Python 3.12.
5. Переключение бота на webhook:
   - В коде реализован запуск через `run_webhook(...)` на пути `/webhook`.
   - Для Railway убран fallback на polling, чтобы исключить конфликты `getUpdates`.
6. Настройка Telegram webhook:
   - Выполнен запрос `setWebhook` на URL Railway.
   - Получен успешный ответ `Webhook was set`.

### С какими проблемами столкнулись

1. Ошибка сборки зависимостей на Railway:
   - `pandas==2.1.4` падал на Python 3.13 (`metadata-generation-failed`).
2. Конфликт режимов Telegram:
   - Ошибки `409 Conflict` из-за одновременного polling (`getUpdates`) и активного webhook.
3. Ошибка при вызове Telegram API:
   - `404 Not Found` из-за неверного формата URL (токен был вставлен в угловых скобках).

### Как решили

1. Для ошибки сборки:
   - Зафиксирована версия Python 3.12 для Railway через `.python-version` и `nixpacks.toml`.
2. Для `409 Conflict`:
   - Остановлены локальные запуски `python bot.py`.
   - Бот переведен в webhook-режим, для Railway отключен fallback на polling.
3. Для `404 Not Found`:
   - Использован корректный URL Telegram API без `< >`.


