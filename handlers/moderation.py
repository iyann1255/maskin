from telegram import Update
from telegram.ext import ContextTypes

import db
from config import RATE_LIMIT_ENABLED, RATE_WINDOW_SEC, RATE_MAX_MSG

async def gate_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Return True if allowed, False if rate-limited.
    Blacklist / auto-block: DIHAPUS total.
    """
    if not RATE_LIMIT_ENABLED:
        return True

    user = update.effective_user
    if not user:
        return False

    uid = user.id

    # whitelist bypass
    if db.is_whitelisted(uid):
        return True

    ok = db.rate_check_and_inc(uid, RATE_WINDOW_SEC, RATE_MAX_MSG)
    if ok:
        return True

    await _reply(update, "Kebanyakan pesan dalam waktu singkat. Coba lagi sebentar ya.")
    return False

async def _reply(update: Update, text: str):
    if update.message:
        await update.message.reply_text(text)
    elif update.callback_query:
        await update.callback_query.answer(text, show_alert=True)
