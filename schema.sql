-- ════════════════════════════════════════════════════════════════
--  Arabic Telegram Verification Bot — Database Schema
--  مخطط قاعدة البيانات للبوت العربي للتحقق
-- ════════════════════════════════════════════════════════════════

-- ── Table 1: pending_users ──────────────────────────────────────
-- Stores users who are currently undergoing verification.
-- يخزن المستخدمين الذين يخضعون حالياً للتحقق.
CREATE TABLE IF NOT EXISTS pending_users (
    user_id          INTEGER NOT NULL,          -- Telegram User ID
    group_id         INTEGER NOT NULL,          -- Telegram Chat/Group ID
    correct_answer   TEXT    NOT NULL,          -- Expected answer (normalized)
    question_type    TEXT    NOT NULL           -- 'button' | 'text'
                     DEFAULT 'button',
    expiry_time      REAL    NOT NULL,          -- Unix timestamp when the challenge expires
    challenge_msg_id INTEGER,                   -- Message ID of the bot's challenge message
    join_msg_id      INTEGER,                   -- Message ID of the Telegram join notification
    attempts         INTEGER NOT NULL           -- Number of wrong attempts so far
                     DEFAULT 0,
    question_text    TEXT,                      -- Original question (for logging/debugging)
    PRIMARY KEY (user_id, group_id)
);

-- Index for fast expiry sweeps
CREATE INDEX IF NOT EXISTS idx_pending_expiry ON pending_users (expiry_time);

-- ── Table 2: blacklist ──────────────────────────────────────────
-- Tracks temporarily or permanently banned users per group.
-- يتتبع المستخدمين المحظورين مؤقتاً أو بشكل دائم لكل مجموعة.
CREATE TABLE IF NOT EXISTS blacklist (
    user_id      INTEGER NOT NULL,              -- Telegram User ID
    group_id     INTEGER NOT NULL,              -- Telegram Chat/Group ID
    expiry_time  REAL    NOT NULL,              -- Unix timestamp when the ban expires (0 = permanent)
    reason       TEXT    DEFAULT               -- Reason code for the ban
                 'verification_failure',
    PRIMARY KEY (user_id, group_id)
);

-- Index for fast blacklist lookups
CREATE INDEX IF NOT EXISTS idx_blacklist_expiry ON blacklist (expiry_time);

-- ── Table 3: verification_log ───────────────────────────────────
-- Immutable audit log of all verification events.
-- سجل تدقيق غير قابل للتغيير لجميع أحداث التحقق.
CREATE TABLE IF NOT EXISTS verification_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,              -- Telegram User ID
    group_id    INTEGER NOT NULL,              -- Telegram Chat/Group ID
    event       TEXT    NOT NULL,             -- 'join' | 'pass' | 'fail' | 'timeout' | 'kick'
    timestamp   REAL    NOT NULL              -- Unix timestamp of the event
);

-- Index for time-range queries (analytics / admin reports)
CREATE INDEX IF NOT EXISTS idx_log_group_time ON verification_log (group_id, timestamp DESC);

-- ════════════════════════════════════════════════════════════════
--  Useful Queries / استعلامات مفيدة
-- ════════════════════════════════════════════════════════════════

-- List all currently pending users in a specific group:
-- SELECT * FROM pending_users WHERE group_id = <CHAT_ID>;

-- Check if a user is actively blacklisted:
-- SELECT * FROM blacklist WHERE user_id = <USER_ID> AND expiry_time > strftime('%s','now');

-- Pass/Fail ratio for a group in the last 7 days:
-- SELECT event, COUNT(*) FROM verification_log
--   WHERE group_id = <CHAT_ID>
--     AND timestamp > strftime('%s','now','-7 days')
--   GROUP BY event;

-- Clean up expired blacklist entries (run periodically):
-- DELETE FROM blacklist WHERE expiry_time <= strftime('%s','now');
