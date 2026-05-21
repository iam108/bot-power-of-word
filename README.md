# 40-дневный вызов — Telegram бот

## Что делает

- 09:45 — присылает в группу кнопки для утренних целей
- 21:45 — кнопки для вечерних отчётов
- `/stats` — статистика по всем дням
- `/today` — кнопки вручную в любой момент

## Деплой на Railway (бесплатно)

### 1. Создай бота
1. Открой @BotFather в Telegram
2. `/newbot` → задай имя и username
3. Скопируй токен (вида `123456:ABC-DEF...`)

### 2. Получи ID группы
1. Добавь бота в свою группу
2. Сделай его администратором
3. Напиши в группе любое сообщение
4. Открой в браузере:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
5. Найди `"chat":{"id": -XXXXXXXXX}` — это и есть GROUP_CHAT_ID (отрицательное число)

### 3. Задеплой на Railway
1. Зайди на https://railway.app и создай аккаунт (через GitHub)
2. New Project → Deploy from GitHub repo
3. Загрузи эти файлы в репозиторий на GitHub
4. В Railway → Variables добавь:

```
BOT_TOKEN      = 123456:ABC-DEF...
GROUP_CHAT_ID  = -1001234567890
START_DATE     = 2025-01-20        # дата начала вызова (YYYY-MM-DD)
TZ             = Europe/Moscow     # или Europe/Kyiv, Asia/Almaty и т.д.
```

5. Deploy — готово!

### Альтернатива: запуск локально
```bash
pip install -r requirements.txt
export BOT_TOKEN="..."
export GROUP_CHAT_ID="-100..."
export START_DATE="2025-01-20"
python bot.py
```

## Структура файлов
```
bot.py          — основная логика бота
db.py           — база данных SQLite
requirements.txt
railway.toml    — конфиг для Railway
```
