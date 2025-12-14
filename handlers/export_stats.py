import io
import json
import csv

from telegram import Update
from telegram.ext import ContextTypes

import db
from config import OWNER_ID

async def cmd_exportcsv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not u or not update.message:
        return
    if not db.is_admin(u.id, OWNER_ID):
        return await update.message.reply_text("Nope. Kamu bukan admin.")

    rows = db.export_feedback_rows(limit=5000)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id","user_id","category","description","attachment_type","created_at","dedup_of","dup_count"])
    for r in rows:
        w.writerow([
            r["id"], r["user_id"], r["category"], r["description"],
            r["attachment_type"], r["created_at"], r["dedup_of"], r["dup_count"]
        ])
    data = buf.getvalue().encode("utf-8")
    await update.message.reply_document(document=data, filename="feedback_export.csv", caption="Export CSV")

async def cmd_exportjson(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not u or not update.message:
        return
    if not db.is_admin(u.id, OWNER_ID):
        return await update.message.reply_text("Nope. Kamu bukan admin.")
    rows = db.export_feedback_rows(limit=5000)
    data = json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")
    await update.message.reply_document(document=data, filename="feedback_export.json", caption="Export JSON")

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not u or not update.message:
        return
    if not db.is_admin(u.id, OWNER_ID):
        return await update.message.reply_text("Nope. Kamu bukan admin.")

    snap = db.stats_snapshot()
    auto_blocked = db.get_counter("auto_blocked")
    created = db.get_counter("feedback_created")

    text = (
        "📊 Stats (tanpa tiket)\n"
        f"- Users: {snap['users']}\n"
        f"- Feedback total: {snap['feedback']}\n"
        f"- Feedback created counter: {created}\n"
        f"- Auto-blocked: {auto_blocked}\n"
        f"- Blacklist size: {snap['blacklist']}\n"
        f"- Whitelist size: {snap['whitelist']}\n"
        f"- Opt-in users: {len(db.export_users_optin())}\n"
    )
    await update.message.reply_text(text)
