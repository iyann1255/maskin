from telegram import Update
from telegram.ext import ContextTypes

import db
from config import OWNER_ID

async def on_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.reply_to_message:
        return

    admin = update.effective_user
    if not admin:
        return

    if not db.is_admin(admin.id, OWNER_ID):
        return

    admin_chat_id = msg.chat_id
    replied_id = msg.reply_to_message.message_id

    mapping = db.relay_get(admin_chat_id, replied_id)
    if not mapping:
        return

    user_id = int(mapping["user_id"])

    try:
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=admin_chat_id,
            message_id=msg.message_id
        )
        await msg.reply_text("✅ Terkirim ke user.")
    except Exception as e:
        print(f"[ERROR] relay failed: {e}")
        if msg.text:
            try:
                await context.bot.send_message(chat_id=user_id, text=msg.text)
                await msg.reply_text("✅ Terkirim (fallback teks).")
            except Exception as e2:
                print(f"[ERROR] relay fallback failed: {e2}")
