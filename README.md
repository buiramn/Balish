# 🥐 Balish Admin Bot

**@balish_menu_bot** — bālish мәзірін басқаратын Telegram боты.

Мәзір элементтерін қосу, өзгерту және жою — тікелей Telegram арқылы. Өзгерістер `balish-menu.json` файлына сақталып, сайт автоматты жаңарады.

---

## Мүмкіндіктер

| | |
|---|---|
| 📋 | Мәзірді санат бойынша көру |
| ➕ | Жаңа тағам қосу |
| ✏️ | Тағам ақпаратын өзгерту |
| 🗑 | Тағамды жою |

---

## Орнату

### 1. Репозиторийді клондау
```bash
git clone https://github.com/yourusername/balish-bot.git
cd balish-bot
```

### 2. Тәуелділіктерді орнату
```bash
pip install -r requirements.txt
```

### 3. `.env` файлын жасау
```bash
cp .env.example .env
```
`.env` файлын ашып, токенді қосыңыз:
```
BOT_TOKEN=your_telegram_bot_token_here
```

### 4. Іске қосу
```bash
python balish_bot.py
```

---

## Файлдар құрылымы

```
balish-bot/
├── balish_bot.py       # Бот коды
├── balish-menu.json    # Мәзір деректері
├── index.html          # Сайт (опционал)
├── requirements.txt    # Python тәуелділіктері
├── .env                # Токен (GitHub-қа жүктемеңіз!)
├── .env.example        # .env үлгісі
└── .gitignore
```

---

## ⚠️ Маңызды

- `.env` файлын **ешқашан** GitHub-қа жүктемеңіз
- `.gitignore` файлы `.env`-ді автоматты қорғайды
- Бот пен `balish-menu.json` **бір қалтада** болуы керек
