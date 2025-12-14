from telegram import Update
from telegram.ext import ContextTypes

import db
from config import OWNER_ID

async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not u or not update.message:
        return
    if not db.is_admin(u.id, OWNER_ID):
        return await update.message.reply_text("Nope. Kamu bukan admin.")
    if not context.args:
        return await update.message.reply_text("Usage: /broadcast <text>")

    text = " ".join(context.args).strip()
    targets = db.export_users_optin()
    sent = 0
    failed = 0

    await update.message.reply_text(f"Mulai broadcast ke {len(targets)} user opt-in...")

    for uid in targets:
        try:
            await context.bot.send_message(chat_id=uid, text=text)
            sent += 1
        except Exception:
            failed += 1

    await update.message.reply_text(f"Selesai. Sent={sent}, Failed={failed}")
