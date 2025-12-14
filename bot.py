from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

import db
from config import BOT_TOKEN, OWNER_ID, ADMIN_LOG_CHAT_ID, DEFAULT_OPT_IN
from handlers.moderation import gate_user
from handlers.user_flow import (
    cmd_start, cmd_new, cb_category, on_user_message, cmd_skip,
    cmd_optin, cmd_optout
)
from handlers.relay import on_admin_reply
from handlers.admin_panel import (
    cmd_admins, cmd_addadmin, cmd_deladmin,
    cmd_whitelist, cmd_unwhitelist,
    cmd_note, cmd_notes
)
from handlers.export_stats import cmd_exportcsv, cmd_exportjson, cmd_stats
from handlers.broadcast import cmd_broadcast
from utils import HELP_ADMIN

def _admin_targets():
    """
    Untuk kesederhanaan: semua feedback masuk ke ADMIN_LOG_CHAT_ID kalau diset.
    Kalau tidak diset, minimal masuk ke owner (DM).
    Kamu bisa tambah mode: kirim ke semua admin DM kalau mau.
    """
    if ADMIN_LOG_CHAT_ID != 0:
        return [ADMIN_LOG_CHAT_ID]
    return [OWNER_ID]

async def precheck(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    # Ensure users table exists / first seen
    if update.effective_user:
        db.ensure_user(update.effective_user.id, DEFAULT_OPT_IN)
    # gate user (rate limit + blacklist + auto-block)
    return await gate_user(update, context)

async def help_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not u or not update.message:
        return
    if not db.is_admin(u.id, OWNER_ID):
        return await update.message.reply_text("Nope. Kamu bukan admin.")
    await update.message.reply_text(HELP_ADMIN)

async def user_message_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await precheck(update, context):
        return
    await on_user_message(update, context, admin_targets=_admin_targets())

async def skip_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await precheck(update, context):
        return
    await cmd_skip(update, context, admin_targets=_admin_targets())

async def start_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await precheck(update, context):
        return
    await cmd_start(update, context)

async def new_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await precheck(update, context):
        return
    await cmd_new(update, context)

async def cb_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await precheck(update, context):
        return
    await cb_category(update, context)

def main():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN belum di-set.")
    if OWNER_ID == 0:
        raise SystemExit("OWNER_ID belum di-set.")
    db.init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    # user commands
    app.add_handler(CommandHandler("start", start_entry))
    app.add_handler(CommandHandler("new", new_entry))
    app.add_handler(CommandHandler("skip", skip_entry))
    app.add_handler(CommandHandler("optin", cmd_optin))
    app.add_handler(CommandHandler("optout", cmd_optout))

    # admin panel
    app.add_handler(CommandHandler("helpadmin", help_admin))
    app.add_handler(CommandHandler("admins", cmd_admins))
    app.add_handler(CommandHandler("addadmin", cmd_addadmin))
    app.add_handler(CommandHandler("deladmin", cmd_deladmin))
    app.add_handler(CommandHandler("whitelist", cmd_whitelist))
    app.add_handler(CommandHandler("unwhitelist", cmd_unwhitelist))
    app.add_handler(CommandHandler("note", cmd_note))
    app.add_handler(CommandHandler("notes", cmd_notes))
    app.add_handler(CommandHandler("exportcsv", cmd_exportcsv))
    app.add_handler(CommandHandler("exportjson", cmd_exportjson))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))

    # callbacks
    app.add_handler(CallbackQueryHandler(cb_entry, pattern=r"^cat:"))

    # relay admin reply -> user (only works when admin replies to bot's message in admin log)
    app.add_handler(MessageHandler(filters.REPLY & ~filters.COMMAND, on_admin_reply))

    # all other user messages
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, user_message_entry))

    print("Feedback bot modular running...")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
