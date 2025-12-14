from telegram import Update
from telegram.ext import ContextTypes

import db
from config import OWNER_ID

def _only_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

async def cmd_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not u or not update.message:
        return
    if not db.is_admin(u.id, OWNER_ID):
        return await update.message.reply_text("Nope. Kamu bukan admin.")
    admins = db.list_admins()
    text = "Admin list:\n" + "\n".join([f"- {a}" for a in admins]) if admins else "Belum ada admin tambahan (owner doang)."
    await update.message.reply_text(text)

async def cmd_addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not u or not update.message:
        return
    if not _only_owner(u.id):
        return await update.message.reply_text("Hanya owner yang bisa add admin.")
    if not context.args:
        return await update.message.reply_text("Usage: /addadmin <user_id>")
    try:
        uid = int(context.args[0])
    except:
        return await update.message.reply_text("user_id harus angka.")
    db.add_admin(uid)
    await update.message.reply_text(f"OK. Admin ditambah: {uid}")

async def cmd_deladmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not u or not update.message:
        return
    if not _only_owner(u.id):
        return await update.message.reply_text("Hanya owner yang bisa del admin.")
    if not context.args:
        return await update.message.reply_text("Usage: /deladmin <user_id>")
    try:
        uid = int(context.args[0])
    except:
        return await update.message.reply_text("user_id harus angka.")
    db.del_admin(uid)
    await update.message.reply_text(f"OK. Admin dihapus: {uid}")

async def cmd_whitelist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not u or not update.message:
        return
    if not db.is_admin(u.id, OWNER_ID):
        return await update.message.reply_text("Nope. Kamu bukan admin.")
    if not context.args:
        return await update.message.reply_text("Usage: /whitelist <user_id> [note]")
    try:
        uid = int(context.args[0])
    except:
        return await update.message.reply_text("user_id harus angka.")
    note = " ".join(context.args[1:]) if len(context.args) > 1 else ""
    db.whitelist_add(uid, note=note)
    await update.message.reply_text(f"OK. Whitelist: {uid}")

async def cmd_unwhitelist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not u or not update.message:
        return
    if not db.is_admin(u.id, OWNER_ID):
        return await update.message.reply_text("Nope. Kamu bukan admin.")
    if not context.args:
        return await update.message.reply_text("Usage: /unwhitelist <user_id>")
    try:
        uid = int(context.args[0])
    except:
        return await update.message.reply_text("user_id harus angka.")
    db.whitelist_del(uid)
    await update.message.reply_text(f"OK. Unwhitelist: {uid}")

async def cmd_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not u or not update.message:
        return
    if not db.is_admin(u.id, OWNER_ID):
        return await update.message.reply_text("Nope. Kamu bukan admin.")
    if len(context.args) < 2:
        return await update.message.reply_text("Usage: /note <feedback_id> <text>")
    try:
        fid = int(context.args[0])
    except:
        return await update.message.reply_text("feedback_id harus angka.")
    note = " ".join(context.args[1:])
    if not db.feedback_get(fid):
        return await update.message.reply_text("Feedback ID tidak ditemukan.")
    nid = db.add_note(fid, u.id, note)
    await update.message.reply_text(f"OK. Note tersimpan (note_id={nid}).")

async def cmd_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not u or not update.message:
        return
    if not db.is_admin(u.id, OWNER_ID):
        return await update.message.reply_text("Nope. Kamu bukan admin.")
    if not context.args:
        return await update.message.reply_text("Usage: /notes <feedback_id>")
    try:
        fid = int(context.args[0])
    except:
        return await update.message.reply_text("feedback_id harus angka.")
    items = db.list_notes(fid, limit=10)
    if not items:
        return await update.message.reply_text("Belum ada note.")
    text = "Notes terakhir:\n" + "\n".join([f"- [{x['created_at']}] {x['admin_id']}: {x['note']}" for x in reversed(items)])
    await update.message.reply_text(text)

