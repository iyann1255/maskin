from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import db
from utils import category_keyboard, safe_user_header, fmt_admin_post, HELP_USER, CATEGORY_LABEL
from config import DEFAULT_OPT_IN

STEP_PICK_CATEGORY = "PICK_CATEGORY"
STEP_WAIT_DESC = "WAIT_DESC"
STEP_WAIT_ATTACH = "WAIT_ATTACH"

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user:
        db.ensure_user(user.id, DEFAULT_OPT_IN)
    await update.message.reply_text(HELP_USER)

async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    db.ensure_user(user.id, DEFAULT_OPT_IN)
    db.wizard_set(user.id, STEP_PICK_CATEGORY)
    await update.message.reply_text("Pilih kategori masukan:", reply_markup=category_keyboard())

async def cb_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user = update.effective_user
    if not q or not user:
        return
    await q.answer()

    data = q.data or ""
    if not data.startswith("cat:"):
        return

    key = data.split(":", 1)[1]
    if key == "CANCEL":
        db.wizard_clear(user.id)
        await q.edit_message_text("Dibatalkan. Kalau mau mulai lagi ketik /new")
        return

    db.wizard_set(user.id, STEP_WAIT_DESC, category=key)
    await q.edit_message_text(f"Oke. Kategori: {CATEGORY_LABEL.get(key, key)}\n\nSekarang kirim deskripsi singkat (teks).")

async def on_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_targets: list[int]):
    msg = update.message
    user = update.effective_user
    if not msg or not user:
        return

    db.ensure_user(user.id, DEFAULT_OPT_IN)

    st = db.wizard_get(user.id)
    if not st:
        await msg.reply_text("Kalau mau kirim masukan yang rapi, ketik /new dulu ya.")
        return

    step = st.get("step")

    if step == STEP_WAIT_DESC:
        if not msg.text or len(msg.text.strip()) < 5:
            await msg.reply_text("Deskripsinya minimal 5 karakter ya. Coba kirim lagi.")
            return
        db.wizard_set(user.id, STEP_WAIT_ATTACH, description=msg.text.strip())
        await msg.reply_text(
            "Sip. Kalau ada bukti (foto/video/file), kirim sekarang.\n"
            "Kalau tidak ada, ketik /skip"
        )
        return

    if step == STEP_WAIT_ATTACH:
        atype, fid, uniq = _extract_attachment(msg)
        if not atype:
            await msg.reply_text("Aku nunggu file bukti ya. Kalau mau lanjut tanpa bukti, ketik /skip")
            return

        db.wizard_set(user.id, STEP_WAIT_ATTACH, attachment_type=atype, attachment_file_id=fid, attachment_unique_id=uniq)
        await _finalize_submit(update, context, admin_targets)
        return

    if step == STEP_PICK_CATEGORY:
        await msg.reply_text("Pilih kategori dulu dari tombol ya:", reply_markup=category_keyboard())
        return

    await msg.reply_text("State kamu agak ngaco. Ketik /new untuk mulai ulang.")
    db.wizard_clear(user.id)

async def cmd_skip(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_targets: list[int]):
    user = update.effective_user
    if not user or not update.message:
        return
    st = db.wizard_get(user.id)
    if not st or st.get("step") != STEP_WAIT_ATTACH:
        return await update.message.reply_text("Belum ada proses yang bisa di-skip. Mulai pakai /new")
    await _finalize_submit(update, context, admin_targets)

def _extract_attachment(msg):
    if msg.document:
        return ("document", msg.document.file_id, msg.document.file_unique_id)
    if msg.video:
        return ("video", msg.video.file_id, msg.video.file_unique_id)
    if msg.photo:
        p = msg.photo[-1]
        return ("photo", p.file_id, p.file_unique_id)
    return (None, None, None)

async def _finalize_submit(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_targets: list[int]):
    msg = update.message
    user = update.effective_user
    if not msg or not user:
        return

    st = db.wizard_get(user.id)
    if not st or not st.get("category") or not st.get("description"):
        await msg.reply_text("Data masukan belum lengkap. Mulai lagi pakai /new")
        db.wizard_clear(user.id)
        return

    cat_key = st["category"]
    cat_label = CATEGORY_LABEL.get(cat_key, cat_key)
    desc = st["description"]
    atype = st.get("attachment_type")
    afid = st.get("attachment_file_id")
    auniq = st.get("attachment_unique_id")

    fid, dedup_of = db.create_feedback(
        user_id=user.id,
        category=cat_label,
        description=desc,
        attachment_type=atype,
        attachment_file_id=afid,
        attachment_unique_id=auniq
    )
    db.inc_counter("feedback_created", 1)

    header = safe_user_header(user)
    text = fmt_admin_post(header, cat_label, desc, fid, dedup_of)

    for chat_id in admin_targets:
        try:
            sent = await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)
            db.relay_put(chat_id, sent.message_id, user.id, fid)

            if atype and afid:
                if atype == "photo":
                    sent2 = await context.bot.send_photo(
                        chat_id=chat_id, photo=afid,
                        caption=f"Attachment for <code>{fid}</code>",
                        parse_mode=ParseMode.HTML
                    )
                    db.relay_put(chat_id, sent2.message_id, user.id, fid)
                elif atype == "video":
                    sent2 = await context.bot.send_video(
                        chat_id=chat_id, video=afid,
                        caption=f"Attachment for <code>{fid}</code>",
                        parse_mode=ParseMode.HTML
                    )
                    db.relay_put(chat_id, sent2.message_id, user.id, fid)
                elif atype == "document":
                    sent2 = await context.bot.send_document(
                        chat_id=chat_id, document=afid,
                        caption=f"Attachment for <code>{fid}</code>",
                        parse_mode=ParseMode.HTML
                    )
                    db.relay_put(chat_id, sent2.message_id, user.id, fid)

        except Exception as e:
            print(f"[WARN] send to admin chat {chat_id} failed: {e}")

    db.wizard_clear(user.id)

    if dedup_of:
        await msg.reply_text(f"Masukan terkirim. ID: {fid}\nCatatan: terdeteksi duplicate (mirip laporan sebelumnya).")
    else:
        await msg.reply_text(f"Masukan terkirim. ID: {fid}\nKalau admin bales, masuk ke sini.")

async def cmd_optin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not update.message:
        return
    db.ensure_user(user.id, DEFAULT_OPT_IN)
    db.set_opt_in(user.id, True)
    await update.message.reply_text("Siap, kamu sekarang opt-in broadcast.")

async def cmd_optout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not update.message:
        return
    db.ensure_user(user.id, DEFAULT_OPT_IN)
    db.set_opt_in(user.id, False)
    await update.message.reply_text("Oke, kamu opt-out broadcast.")
