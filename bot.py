"""
╔══════════════════════════════════════════════════════════════════╗
║         Arabic High-Security Telegram Verification Bot           ║
║         بوت التحقق العربي عالي الأمان لمجموعات تيليغرام         ║
╚══════════════════════════════════════════════════════════════════╝

Requirements:
    pip install python-telegram-bot==20.7 aiosqlite

Usage:
    1. Set BOT_TOKEN in the Config class below.
    2. Add the bot to your group as an administrator.
    3. Grant it: Ban users, Delete messages, Restrict members.
    4. Run: python bot.py
"""

import asyncio
import logging
import random
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Optional

import aiosqlite
from telegram import (
    Bot,
    Chat,
    ChatMember,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ─────────────────────────────────────────────
#  Logging Setup
# ─────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ArabicVerifyBot")


# ─────────────────────────────────────────────
#  Configuration Class
# ─────────────────────────────────────────────
class Config:
    """
    Central configuration — edit these values to customize the bot.
    تكوين مركزي — قم بتعديل هذه القيم لتخصيص البوت.
    """

    # ── Core ────────────────────────────────────────────────────────
    BOT_TOKEN: str = "YOUR_BOT_TOKEN_HERE"        # ← ضع توكن البوت هنا
    DATABASE_PATH: str = "database.db"

    # ── Timers (seconds) ────────────────────────────────────────────
    VERIFICATION_TIMEOUT: int = 60                 # وقت الإجابة بالثواني
    BAN_DURATION_MINUTES: int = 30                 # مدة الحظر عند الفشل
    HUMAN_DELAY_SECONDS: float = 1.5               # الحد الأدنى للرد البشري

    # ── Behavior ────────────────────────────────────────────────────
    DELETE_MESSAGES_ON_CLEANUP: bool = True        # حذف الرسائل بعد التحقق
    KICK_ON_TIMEOUT: bool = True                   # طرد المستخدم عند انتهاء الوقت
    MAX_ATTEMPTS: int = 2                          # عدد المحاولات المسموح بها

    # ── Question Pool ────────────────────────────────────────────────
    # كل سؤال: (نص_السؤال, الإجابة_الصحيحة, [خيارات_إضافية_للأزرار_أو_None_للنص])
    # None في خيارات = إدخال نصي ، قائمة = أزرار اختيار
    QUESTIONS = [
        # ── Math (Inline Buttons) ────────────────────────────────────
        {
            "text": "🔢 ما هو ناتج جمع *تسعة* و*خمسة*؟\nأجب بالأرقام.",
            "answer": "14",
            "choices": ["11", "14", "16", "19"],
            "type": "button",
        },
        {
            "text": "🔢 كم يساوي *ثمانية* ناقص *ثلاثة*؟\nأجب بالأرقام.",
            "answer": "5",
            "choices": ["3", "5", "4", "6"],
            "type": "button",
        },
        {
            "text": "🔢 حاصل ضرب *أربعة* في *ثلاثة* يساوي؟",
            "answer": "12",
            "choices": ["9", "16", "12", "7"],
            "type": "button",
        },
        {
            "text": "🔢 ما هو ناتج *خمسة عشر* ÷ *ثلاثة*؟",
            "answer": "5",
            "choices": ["3", "6", "5", "4"],
            "type": "button",
        },
        # ── Word/Logic (Text Input) ──────────────────────────────────
        {
            "text": (
                "📝 اكتب الكلمة *الثالثة* من هذه الجملة:\n"
                "«البرمجة علمٌ ممتعٌ جداً»"
            ),
            "answer": "ممتعٌ",
            "choices": None,
            "type": "text",
        },
        {
            "text": (
                "📝 ما هي الكلمة *الثانية* في الجملة التالية؟\n"
                "«السماء زرقاء جميلة»"
            ),
            "answer": "زرقاء",
            "choices": None,
            "type": "text",
        },
        {
            "text": (
                "📝 أكمل: الشمس تشرق من ال___؟\n"
                "(اكتب كلمة واحدة فقط)"
            ),
            "answer": "شرق",
            "choices": None,
            "type": "text",
        },
        # ── Contextual Arabic (Buttons) ──────────────────────────────
        {
            "text": "🌙 ما هو الشهر الذي يصوم فيه المسلمون؟",
            "answer": "رمضان",
            "choices": ["شعبان", "رمضان", "محرم", "ذو الحجة"],
            "type": "button",
        },
        {
            "text": "🗓️ كم عدد أيام الأسبوع؟",
            "answer": "7",
            "choices": ["5", "6", "7", "8"],
            "type": "button",
        },
        {
            "text": "🌍 ما عاصمة المملكة العربية السعودية؟",
            "answer": "الرياض",
            "choices": ["جدة", "مكة", "الرياض", "الدمام"],
            "type": "button",
        },
        {
            "text": "📖 كم عدد حروف كلمة «تيليغرام»؟",
            "answer": "8",
            "choices": ["7", "8", "9", "10"],
            "type": "button",
        },
    ]


# ─────────────────────────────────────────────
#  Database Manager
# ─────────────────────────────────────────────
class Database:
    """
    Async SQLite wrapper for managing pending verifications and blacklists.
    مدير قاعدة بيانات SQLite غير متزامن لإدارة التحقق والقائمة السوداء.
    """

    SCHEMA = """
    -- Users currently under verification (pending)
    CREATE TABLE IF NOT EXISTS pending_users (
        user_id          INTEGER NOT NULL,
        group_id         INTEGER NOT NULL,
        correct_answer   TEXT    NOT NULL,
        question_type    TEXT    NOT NULL DEFAULT 'button',
        expiry_time      REAL    NOT NULL,
        challenge_msg_id INTEGER,
        join_msg_id      INTEGER,
        attempts         INTEGER NOT NULL DEFAULT 0,
        question_text    TEXT,
        PRIMARY KEY (user_id, group_id)
    );

    -- Users permanently or temporarily banned
    CREATE TABLE IF NOT EXISTS blacklist (
        user_id      INTEGER NOT NULL,
        group_id     INTEGER NOT NULL,
        expiry_time  REAL    NOT NULL,
        reason       TEXT    DEFAULT 'verification_failure',
        PRIMARY KEY (user_id, group_id)
    );

    -- Audit log for all verification events
    CREATE TABLE IF NOT EXISTS verification_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL,
        group_id    INTEGER NOT NULL,
        event       TEXT    NOT NULL,   -- 'join','pass','fail','timeout','kick'
        timestamp   REAL    NOT NULL
    );
    """

    def __init__(self, path: str):
        self.path = path

    async def init(self):
        """Initialize the database and create tables."""
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(self.SCHEMA)
            await db.commit()
        logger.info("✅ Database initialized at '%s'", self.path)

    async def add_pending(
        self,
        user_id: int,
        group_id: int,
        answer: str,
        q_type: str,
        expiry: float,
        challenge_msg_id: Optional[int],
        join_msg_id: Optional[int],
        question_text: str,
    ):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO pending_users
                (user_id, group_id, correct_answer, question_type,
                 expiry_time, challenge_msg_id, join_msg_id, attempts, question_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (user_id, group_id, answer, q_type, expiry,
                 challenge_msg_id, join_msg_id, question_text),
            )
            await db.commit()

    async def get_pending(self, user_id: int, group_id: int) -> Optional[dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM pending_users WHERE user_id=? AND group_id=?",
                (user_id, group_id),
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def remove_pending(self, user_id: int, group_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "DELETE FROM pending_users WHERE user_id=? AND group_id=?",
                (user_id, group_id),
            )
            await db.commit()

    async def increment_attempts(self, user_id: int, group_id: int) -> int:
        """Increment attempt counter and return the new value."""
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE pending_users SET attempts = attempts + 1 WHERE user_id=? AND group_id=?",
                (user_id, group_id),
            )
            await db.commit()
            async with db.execute(
                "SELECT attempts FROM pending_users WHERE user_id=? AND group_id=?",
                (user_id, group_id),
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def add_blacklist(self, user_id: int, group_id: int, expiry: float, reason: str = "verification_failure"):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO blacklist (user_id, group_id, expiry_time, reason) VALUES (?, ?, ?, ?)",
                (user_id, group_id, expiry, reason),
            )
            await db.commit()

    async def is_blacklisted(self, user_id: int, group_id: int) -> bool:
        async with aiosqlite.connect(self.path) as db:
            async with db.execute(
                "SELECT expiry_time FROM blacklist WHERE user_id=? AND group_id=?",
                (user_id, group_id),
            ) as cursor:
                row = await cursor.fetchone()
                if row and row[0] > time.time():
                    return True
                if row:  # Expired — clean up
                    await db.execute(
                        "DELETE FROM blacklist WHERE user_id=? AND group_id=?",
                        (user_id, group_id),
                    )
                    await db.commit()
        return False

    async def log_event(self, user_id: int, group_id: int, event: str):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO verification_log (user_id, group_id, event, timestamp) VALUES (?, ?, ?, ?)",
                (user_id, group_id, event, time.time()),
            )
            await db.commit()

    async def get_all_expired_pending(self) -> list[dict]:
        """Fetch all pending records whose timer has expired."""
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM pending_users WHERE expiry_time <= ?",
                (time.time(),),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]


# ─────────────────────────────────────────────
#  Bot Helper Functions
# ─────────────────────────────────────────────

def build_keyboard(choices: list[str], correct: str) -> InlineKeyboardMarkup:
    """
    Build a randomized 2-column inline keyboard from the choice list.
    بناء لوحة مفاتيح مضمنة عشوائية ثنائية الأعمدة من قائمة الخيارات.
    """
    shuffled = choices[:]
    random.shuffle(shuffled)
    # Pack into rows of 2
    buttons = [
        InlineKeyboardButton(text=opt, callback_data=f"verify:{opt}")
        for opt in shuffled
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(rows)


def normalize_arabic(text: str) -> str:
    """
    Strip diacritics and normalize Arabic text for comparison.
    إزالة التشكيل وتطبيع النص العربي للمقارنة.
    """
    # Remove common Arabic diacritics (tashkeel)
    diacritics = "ًٌٍَُِّْٰٓٔ"
    for d in diacritics:
        text = text.replace(d, "")
    # Normalize alef variants → ا
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ٱ", "ا")
    # Normalize teh marbuta → ه
    text = text.replace("ة", "ه")
    return text.strip().lower()


async def safe_delete(bot: Bot, chat_id: int, message_id: Optional[int]):
    """Delete a message, silently ignoring errors if it's already gone."""
    if not message_id:
        return
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except (BadRequest, Forbidden, TelegramError):
        pass  # Already deleted or no permission — acceptable


async def restrict_user(bot: Bot, chat_id: int, user_id: int):
    """Restrict a user from sending any content in the group."""
    try:
        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=ChatPermissions(
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False,
            ),
        )
    except (BadRequest, Forbidden) as e:
        logger.warning("⚠️  Could not restrict user %d in %d: %s", user_id, chat_id, e)


async def restore_permissions(bot: Bot, chat_id: int, user_id: int):
    """Restore default group permissions after successful verification."""
    try:
        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_change_info=False,
                can_invite_users=True,
                can_pin_messages=False,
            ),
        )
    except (BadRequest, Forbidden) as e:
        logger.warning("⚠️  Could not restore permissions for %d in %d: %s", user_id, chat_id, e)


async def kick_user(bot: Bot, chat_id: int, user_id: int, ban_seconds: int = 0):
    """
    Ban a user temporarily. Telegram's ban_until_date 0 = permanent,
    so we compute an absolute timestamp for the temp-ban duration.
    """
    try:
        until = datetime.now() + timedelta(seconds=ban_seconds) if ban_seconds else None
        await bot.ban_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            until_date=until,
            revoke_messages=False,
        )
        logger.info("🔨 Banned user %d from group %d (duration: %ds)", user_id, chat_id, ban_seconds)
    except (BadRequest, Forbidden) as e:
        logger.warning("⚠️  Could not ban user %d in %d: %s", user_id, chat_id, e)


async def check_user_profile(bot: Bot, user_id: int) -> dict:
    """
    Optional anti-bot scoring: check if user has profile photo or bio.
    Returns a dict with boolean flags.
    """
    result = {"has_photo": False, "has_bio": False}
    try:
        photos = await bot.get_user_profile_photos(user_id=user_id, limit=1)
        result["has_photo"] = photos.total_count > 0
        # Bio requires getChatMember — not directly available without being in the same chat.
        # Left as an optional hook for future enhancement.
    except (BadRequest, Forbidden, TelegramError):
        pass
    return result


# ─────────────────────────────────────────────
#  Core Verification Engine
# ─────────────────────────────────────────────

async def send_challenge(
    bot: Bot,
    db: Database,
    user_id: int,
    chat_id: int,
    first_name: str,
    join_msg_id: Optional[int],
):
    """
    Pick a random question, restrict the user, and send the challenge message.
    اختر سؤالاً عشوائياً، قيّد المستخدم، وأرسل رسالة التحقق.
    """
    # 1. Restrict the new user immediately
    await restrict_user(bot, chat_id, user_id)

    # 2. Choose a random question
    question = random.choice(Config.QUESTIONS)
    expiry = time.time() + Config.VERIFICATION_TIMEOUT

    # 3. Build the challenge message text
    intro = (
        f"👋 مرحباً *{first_name}*،\n\n"
        f"للحفاظ على أمان المجموعة، يرجى الإجابة على السؤال التالي "
        f"خلال *{Config.VERIFICATION_TIMEOUT} ثانية* وإلا سيتم طردك تلقائياً.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{question['text']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    markup = None
    if question["type"] == "button":
        intro += "⬇️ اختر الإجابة الصحيحة من الأزرار أدناه:"
        markup = build_keyboard(question["choices"], question["answer"])
    else:
        intro += "✏️ اكتب إجابتك في المجموعة مباشرةً."

    # 4. Send the challenge
    try:
        msg = await bot.send_message(
            chat_id=chat_id,
            text=intro,
            parse_mode="Markdown",
            reply_markup=markup,
        )
        challenge_msg_id = msg.message_id
    except (BadRequest, Forbidden, TelegramError) as e:
        logger.error("❌ Failed to send challenge to %d: %s", user_id, e)
        return

    # 5. Persist to DB
    await db.add_pending(
        user_id=user_id,
        group_id=chat_id,
        answer=question["answer"],
        q_type=question["type"],
        expiry=expiry,
        challenge_msg_id=challenge_msg_id,
        join_msg_id=join_msg_id,
        question_text=question["text"],
    )
    await db.log_event(user_id, chat_id, "join")

    logger.info(
        "📨 Challenge sent │ user=%d │ group=%d │ type=%s │ expires_in=%ds",
        user_id, chat_id, question["type"], Config.VERIFICATION_TIMEOUT,
    )


async def handle_verification_pass(
    bot: Bot,
    db: Database,
    record: dict,
    user_id: int,
    first_name: str,
):
    """Handle a correct answer: restore permissions, clean up, log."""
    chat_id = record["group_id"]

    # 1. Restore full permissions
    await restore_permissions(bot, chat_id, user_id)

    # 2. Delete challenge and join messages
    if Config.DELETE_MESSAGES_ON_CLEANUP:
        await safe_delete(bot, chat_id, record.get("challenge_msg_id"))
        await safe_delete(bot, chat_id, record.get("join_msg_id"))

    # 3. Send welcome message
    try:
        welcome = await bot.send_message(
            chat_id=chat_id,
            text=(
                f"✅ *أهلاً وسهلاً {first_name}!*\n"
                "لقد اجتزت التحقق بنجاح. مرحباً بك في المجموعة! 🎉"
            ),
            parse_mode="Markdown",
        )
        # Auto-delete the welcome message after 10 seconds
        asyncio.get_event_loop().call_later(
            10, asyncio.ensure_future, safe_delete(bot, chat_id, welcome.message_id)
        )
    except (BadRequest, Forbidden):
        pass

    # 4. Clean up DB
    await db.remove_pending(user_id, chat_id)
    await db.log_event(user_id, chat_id, "pass")
    logger.info("✅ Verified │ user=%d │ group=%d", user_id, chat_id)


async def handle_verification_fail(
    bot: Bot,
    db: Database,
    record: dict,
    user_id: int,
    reason: str = "wrong_answer",
):
    """Handle a failed verification: kick/ban, clean up, blacklist."""
    chat_id = record["group_id"]
    ban_secs = Config.BAN_DURATION_MINUTES * 60

    # 1. Clean up messages first (before ban revokes access)
    if Config.DELETE_MESSAGES_ON_CLEANUP:
        await safe_delete(bot, chat_id, record.get("challenge_msg_id"))
        await safe_delete(bot, chat_id, record.get("join_msg_id"))

    # 2. Inform the group briefly
    try:
        fail_msg = await bot.send_message(
            chat_id=chat_id,
            text=(
                f"🚫 فشل المستخدم في اجتياز التحقق.\n"
                f"تم طرده لمدة *{Config.BAN_DURATION_MINUTES} دقيقة*."
            ),
            parse_mode="Markdown",
        )
        asyncio.get_event_loop().call_later(
            8, asyncio.ensure_future, safe_delete(bot, chat_id, fail_msg.message_id)
        )
    except (BadRequest, Forbidden):
        pass

    # 3. Ban the user temporarily
    if Config.KICK_ON_TIMEOUT:
        await kick_user(bot, chat_id, user_id, ban_seconds=ban_secs)

    # 4. Add to blacklist and remove from pending
    expiry = time.time() + ban_secs
    await db.add_blacklist(user_id, chat_id, expiry, reason=reason)
    await db.remove_pending(user_id, chat_id)
    await db.log_event(user_id, chat_id, "fail")
    logger.info("❌ Failed │ user=%d │ group=%d │ reason=%s", user_id, chat_id, reason)


# ─────────────────────────────────────────────
#  Handlers
# ─────────────────────────────────────────────

async def on_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Fires when a user joins a group.
    Handler: ChatMemberHandler(on_chat_member_update, ChatMemberHandler.CHAT_MEMBER)
    يُطلق عندما ينضم مستخدم إلى مجموعة.
    """
    db: Database = context.bot_data["db"]
    result = update.chat_member

    # Only care about new members or members who were restricted → became members
    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status

    is_joining = (
        old_status in (ChatMember.LEFT, ChatMember.BANNED)
        and new_status == ChatMember.MEMBER
    )
    if not is_joining:
        return

    user = result.new_chat_member.user
    chat = result.chat

    # Skip bots
    if user.is_bot:
        return

    # Skip if already blacklisted (will be caught by Telegram's own ban, but double-check)
    if await db.is_blacklisted(user.id, chat.id):
        logger.info("🚷 Blacklisted user %d tried to rejoin %d", user.id, chat.id)
        await kick_user(context.bot, chat.id, user.id, ban_seconds=Config.BAN_DURATION_MINUTES * 60)
        return

    # Optional: check profile for anti-bot scoring
    profile = await check_user_profile(context.bot, user.id)
    if not profile["has_photo"]:
        logger.info("ℹ️  User %d has no profile photo (suspicious).", user.id)

    # Attempt to capture the join notification message id
    # (Telegram doesn't expose this directly in chat_member updates; 
    #  we store None and delete whatever we can find via the challenge message cleanup)
    join_msg_id = None

    await send_challenge(
        bot=context.bot,
        db=db,
        user_id=user.id,
        chat_id=chat.id,
        first_name=user.first_name,
        join_msg_id=join_msg_id,
    )


async def on_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Fires when a user presses an inline keyboard button.
    يُطلق عندما يضغط المستخدم على زر في لوحة المفاتيح المضمنة.
    """
    db: Database = context.bot_data["db"]
    query = update.callback_query
    user = query.from_user
    chat = query.message.chat

    # Acknowledge the tap immediately
    await query.answer()

    if not query.data.startswith("verify:"):
        return

    chosen = query.data.split(":", 1)[1]
    record = await db.get_pending(user.id, chat.id)

    # ── Guard: not in pending ────────────────────────────────────────
    if not record:
        await query.answer("⚠️ لا يوجد تحقق نشط لك.", show_alert=True)
        return

    # ── Guard: expired ───────────────────────────────────────────────
    if time.time() > record["expiry_time"]:
        await query.answer("⏰ انتهى وقت التحقق.", show_alert=True)
        await handle_verification_fail(context.bot, db, record, user.id, reason="timeout")
        return

    # ── Guard: wrong user pressing the button ────────────────────────
    # (Anyone in the group can see and press the button; only the target user may answer)
    if query.message.chat_id != chat.id:
        await query.answer("❌ هذا السؤال ليس لك.", show_alert=True)
        return

    # ── Anti-bot human delay check ───────────────────────────────────
    elapsed = time.time() - (record["expiry_time"] - Config.VERIFICATION_TIMEOUT)
    if elapsed < Config.HUMAN_DELAY_SECONDS:
        logger.info("⚡ Instant response from %d — possible bot (elapsed=%.2fs)", user.id, elapsed)
        # Treat as suspicious but do NOT fail immediately; increment attempt instead
        await query.answer("⚠️ الرجاء الانتظار لحظة قبل الإجابة.", show_alert=True)
        return

    # ── Evaluate answer ──────────────────────────────────────────────
    if normalize_arabic(chosen) == normalize_arabic(record["correct_answer"]):
        await handle_verification_pass(context.bot, db, record, user.id, user.first_name)
    else:
        attempts = await db.increment_attempts(user.id, chat.id)
        remaining = Config.MAX_ATTEMPTS - attempts
        if remaining > 0:
            await query.answer(
                f"❌ إجابة خاطئة. لديك {remaining} محاولة/محاولات متبقية.",
                show_alert=True,
            )
        else:
            await query.answer("❌ إجابة خاطئة. تم طردك.", show_alert=True)
            await handle_verification_fail(context.bot, db, record, user.id, reason="wrong_answer")


async def on_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Fires for regular text messages — used for text-input type questions.
    يُطلق عند استقبال رسائل نصية عادية — لأسئلة الإدخال النصي.
    """
    db: Database = context.bot_data["db"]
    msg = update.message
    if not msg or not msg.text:
        return

    user = msg.from_user
    chat = msg.chat

    record = await db.get_pending(user.id, chat.id)
    if not record or record["question_type"] != "text":
        return

    # ── Guard: expired ───────────────────────────────────────────────
    if time.time() > record["expiry_time"]:
        await safe_delete(context.bot, chat.id, msg.message_id)
        await handle_verification_fail(context.bot, db, record, user.id, reason="timeout")
        return

    # ── Anti-bot human delay check ───────────────────────────────────
    elapsed = time.time() - (record["expiry_time"] - Config.VERIFICATION_TIMEOUT)
    if elapsed < Config.HUMAN_DELAY_SECONDS:
        await safe_delete(context.bot, chat.id, msg.message_id)
        try:
            warn = await msg.reply_text("⚠️ الرجاء الانتظار لحظة قبل الإجابة.")
            await asyncio.sleep(3)
            await safe_delete(context.bot, chat.id, warn.message_id)
        except (BadRequest, Forbidden):
            pass
        return

    # ── Delete user's answer message to keep chat clean ─────────────
    await safe_delete(context.bot, chat.id, msg.message_id)

    # ── Evaluate answer ──────────────────────────────────────────────
    if normalize_arabic(msg.text) == normalize_arabic(record["correct_answer"]):
        await handle_verification_pass(context.bot, db, record, user.id, user.first_name)
    else:
        attempts = await db.increment_attempts(user.id, chat.id)
        remaining = Config.MAX_ATTEMPTS - attempts
        if remaining > 0:
            try:
                hint = await context.bot.send_message(
                    chat_id=chat.id,
                    text=f"❌ إجابة خاطئة يا *{user.first_name}*. لديك *{remaining}* محاولة متبقية.",
                    parse_mode="Markdown",
                )
                await asyncio.sleep(4)
                await safe_delete(context.bot, chat.id, hint.message_id)
            except (BadRequest, Forbidden):
                pass
        else:
            await handle_verification_fail(context.bot, db, record, user.id, reason="wrong_answer")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /status — Admin command to see how many users are pending verification.
    أمر المسؤول لعرض عدد المستخدمين في انتظار التحقق.
    """
    if not update.message:
        return
    member = await context.bot.get_chat_member(
        update.message.chat_id, update.message.from_user.id
    )
    if member.status not in (ChatMember.ADMINISTRATOR, ChatMember.OWNER):
        return  # Silently ignore non-admins

    db: Database = context.bot_data["db"]
    async with aiosqlite.connect(Config.DATABASE_PATH) as conn:
        async with conn.execute("SELECT COUNT(*) FROM pending_users WHERE group_id=?",
                                (update.message.chat_id,)) as cur:
            (pending,) = await cur.fetchone()
        async with conn.execute("SELECT COUNT(*) FROM blacklist WHERE group_id=? AND expiry_time > ?",
                                (update.message.chat_id, time.time())) as cur:
            (blacklisted,) = await cur.fetchone()

    await update.message.reply_text(
        f"📊 *إحصائيات التحقق*\n\n"
        f"⏳ في انتظار التحقق: *{pending}*\n"
        f"🚫 في القائمة السوداء: *{blacklisted}*",
        parse_mode="Markdown",
    )


# ─────────────────────────────────────────────
#  Background Timeout Sweeper
# ─────────────────────────────────────────────

async def timeout_sweeper(context: ContextTypes.DEFAULT_TYPE):
    """
    Periodic job: Finds expired pending users and kicks them.
    مهمة دورية: تجد المستخدمين الذين انتهت مهلتهم وتطردهم.
    """
    db: Database = context.bot_data["db"]
    expired = await db.get_all_expired_pending()

    for record in expired:
        user_id = record["user_id"]
        chat_id = record["group_id"]
        logger.info("⏰ Timeout sweeper kicking user=%d from group=%d", user_id, chat_id)
        await handle_verification_fail(context.bot, db, record, user_id, reason="timeout")
        await db.log_event(user_id, chat_id, "timeout")


# ─────────────────────────────────────────────
#  Application Bootstrap
# ─────────────────────────────────────────────

def main():
    """
    Entry point: build the Application, register handlers, start polling.
    نقطة الدخول: بناء التطبيق، تسجيل المعالجات، بدء الاستطلاع.
    """
    if Config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.critical("🛑 Please set your BOT_TOKEN in the Config class before running!")
        return

    # ── Build Application ────────────────────────────────────────────
    app = (
        Application.builder()
        .token(Config.BOT_TOKEN)
        .build()
    )

    # ── Init DB (synchronous bootstrap call) ────────────────────────
    db = Database(Config.DATABASE_PATH)
    app.bot_data["db"] = db

    async def post_init(application: Application):
        await db.init()

    app.post_init = post_init

    # ── Register Handlers ────────────────────────────────────────────

    # 1. New member joins
    app.add_handler(
        ChatMemberHandler(on_chat_member_update, ChatMemberHandler.CHAT_MEMBER)
    )

    # 2. Inline button presses (button-type challenges)
    app.add_handler(CallbackQueryHandler(on_callback_query, pattern=r"^verify:"))

    # 3. Text messages (text-type challenges — only in groups)
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
            on_text_message,
        )
    )

    # 4. Admin status command
    app.add_handler(CommandHandler("status", cmd_status))

    # ── Periodic Timeout Sweeper (every 15 seconds) ──────────────────
    app.job_queue.run_repeating(timeout_sweeper, interval=15, first=15)

    # ── Start ────────────────────────────────────────────────────────
    logger.info("🚀 Bot is starting — waiting for updates...")
    app.run_polling(
        allowed_updates=[
            "chat_member",
            "callback_query",
            "message",
        ],
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
