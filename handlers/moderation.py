from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import ContextTypes

import db
from config import RATE_WINDOW_SEC, RATE_MAX_MSG, AUTO_BLOCK_MINUTES

UTC = timezone.utc

async def gate_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Return True if allowed to proceed, False if blocked.
    """
    user = update.effective_user
    if not user:
        return False

    uid = user.id

    # blacklist active?
    if db.is_blacklisted_active(uid):
        await _reply(update, "Kamu sedang dibatasi akses (blacklist sementara/permanen).")
        return False

    # whitelist bypass
    if db.is_whitelisted(uid):
        return True

    # rate check
    ok = db.rate_check_and_inc(uid, RATE_WINDOW_SEC, RATE_MAX_MSG)
    if ok:
        return True

    # exceeded => auto block
    until = datetime.now(tz=UTC) + timedelta(minutes=AUTO_BLOCK_MINUTES)
    db.blacklist_add(uid, reason="Auto-block: spam / rate limit exceeded", until_iso=until.isoformat())
    db.inc_counter("auto_blocked", 1)
    await _reply(update, f"Kebanyakan pesan dalam waktu singkat. Kamu di-block sementara sampai {until.strftime('%Y-%m-%d %H:%M UTC')}.")
    return False

async def _reply(update: Update, text: str):
    if update.message:
        await update.message.reply_text(text)
    elif update.callback_query:
        await update.callback_query.answer(text, show_alert=True)
