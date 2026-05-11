# 🛡️ Arabic Telegram Verification Bot
### بوت التحقق العربي عالي الأمان لمجموعات تيليغرام

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-v20+-blue?style=for-the-badge&logo=telegram)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)
![Async](https://img.shields.io/badge/Async-asyncio-purple?style=for-the-badge)

**A robust, async Telegram bot that protects Arabic-speaking groups from spam bots using contextual Arabic challenge-response verification.**

</div>

---

## ✨ Features / المميزات

- 🔒 **Instant Restriction** — New members are silenced the moment they join
- 🧠 **11 Arabic Challenges** — Math, logic, and cultural questions in two modes (buttons & text input)
- ⏱️ **60-Second Timer** — Auto-kick on timeout via a background sweeper job
- 🤖 **Anti-Bot Detection** — Human delay check rejects responses under 1.5 seconds
- 🔁 **Configurable Attempts** — 2 wrong answers before a 30-minute ban
- 🧹 **Auto Cleanup** — Challenge and join messages deleted on pass or fail
- 📋 **SQLite Persistence** — Survives restarts; tracks pending sessions, blacklists, and audit logs
- 📊 **Admin `/status` Command** — See live pending/blacklisted counts per group
- 🌍 **Fully in Arabic** — All messages use professional, clear Arabic with `{first_name}` personalization

---

## 📸 Preview / معاينة

```
👋 مرحباً Ahmed،

للحفاظ على أمان المجموعة، يرجى الإجابة على السؤال التالي
خلال 60 ثانية وإلا سيتم طردك تلقائياً.

━━━━━━━━━━━━━━━━━━━━
🔢 ما هو ناتج جمع تسعة وخمسة؟
━━━━━━━━━━━━━━━━━━━━

⬇️ اختر الإجابة الصحيحة من الأزرار أدناه:

  [ 11 ]  [ 14 ]
  [ 16 ]  [ 19 ]
```

---

## 🗂️ Project Structure / هيكل المشروع

```
📦 arabic-verify-bot/
├── 🐍 bot.py           # Main bot — all logic in one file
├── 🗄️ schema.sql       # Database schema with comments & useful queries
├── 🗃️ database.db      # Auto-generated on first run (SQLite)
├── 📄 requirements.txt
└── 📖 README.md
```

---

## ⚙️ Setup / التثبيت

### 1. Clone the repo
```bash
git clone https://github.com/v22YO/arabic-verify-bot.git

cd arabic-verify-bot
```

### 2. Install dependencies
```bash
pip install python-telegram-bot==20.7 aiosqlite
```

### 3. Create your bot
- Open [@BotFather](https://t.me/BotFather) on Telegram
- Send `/newbot` and follow the prompts
- Copy your **Bot Token**

### 4. Configure the bot
Open `bot.py` and edit the `Config` class:
```python
class Config:
    BOT_TOKEN = "123456:ABC-DEF..."   # ← Paste your token here
    VERIFICATION_TIMEOUT = 60          # Seconds to answer
    BAN_DURATION_MINUTES = 30          # Ban length on failure
    MAX_ATTEMPTS = 2                   # Wrong tries allowed
```

### 5. Run
```bash
python bot.py
```

---

## 🔑 Required Bot Permissions / صلاحيات البوت المطلوبة

Add the bot to your group as an **Administrator** with these permissions:

| Permission | Required |
|---|---|
| Ban Members | ✅ |
| Delete Messages | ✅ |
| Restrict Members | ✅ |
| Read Messages | ✅ |

---

## 🛡️ Security Architecture / طبقات الأمان

```
User Joins
    │
    ▼
① Blacklist Check ──── banned? ──→ Re-kick immediately
    │
    ▼
② Instant Restrict (can't send anything)
    │
    ▼
③ Random Arabic Challenge sent (button or text)
    │
    ├── ④ Human Delay Guard (< 1.5s → rejected)
    │
    ├── ⑤ Attempt Limiter (max 2 wrong answers)
    │
    └── ⑥ Background Sweeper (checks every 15s for expired sessions)
              │
    Pass ─────┴───── Fail / Timeout
      │                    │
  Restore perms       Temp-ban 30min
  Welcome message     Add to blacklist
  Cleanup messages    Cleanup messages
```

---

## 🗄️ Database Schema / مخطط قاعدة البيانات

```sql
pending_users      -- Active verification sessions
blacklist          -- Temp/permanent bans with auto-expiry  
verification_log   -- Immutable audit trail (join/pass/fail/timeout)
```

> The database is created automatically at `database.db` on first run.

---

## ❓ Question Pool / بنك الأسئلة

The bot randomly picks from **11 Arabic questions** across two challenge types:

| Type | Example | Input Method |
|---|---|---|
| Math | ما هو ناتج جمع تسعة وخمسة؟ | Inline Buttons |
| Word Logic | اكتب الكلمة الثالثة من «البرمجة علم ممتع جداً» | Text Input |
| Cultural | ما عاصمة المملكة العربية السعودية؟ | Inline Buttons |

To add your own questions, edit `Config.QUESTIONS` in `bot.py`:
```python
{
    "text": "سؤالك هنا؟",
    "answer": "الإجابة",
    "choices": ["خيار1", "خيار2", "الإجابة", "خيار3"],  # None for text input
    "type": "button",  # or "text"
},
```

---

## 📋 Admin Commands / أوامر المسؤول

| Command | Description |
|---|---|
| `/status` | Show pending verifications and blacklisted count for the group |

> Only group administrators can use these commands.

---

## 🔧 Configuration Reference / مرجع الإعدادات

| Setting | Default | Description |
|---|---|---|
| `BOT_TOKEN` | — | Your Telegram Bot Token |
| `VERIFICATION_TIMEOUT` | `60` | Seconds before auto-kick |
| `BAN_DURATION_MINUTES` | `30` | Temp-ban length on failure |
| `HUMAN_DELAY_SECONDS` | `1.5` | Min response time (anti-bot) |
| `MAX_ATTEMPTS` | `2` | Wrong answers before kick |
| `KICK_ON_TIMEOUT` | `True` | Kick user on timeout |
| `DELETE_MESSAGES_ON_CLEANUP` | `True` | Auto-delete challenge messages |

---

## 📦 Dependencies / المتطلبات

```
python-telegram-bot==20.7
aiosqlite
```

Python **3.11+** recommended.

---

## 📜 License

MIT License — free to use, modify, and distribute.

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.

---

<div align="center">
  Made with ❤️ for Arabic Telegram communities
  <br>
  صُنع بـ ❤️ لمجتمعات تيليغرام العربية
</div>
