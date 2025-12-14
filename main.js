import os
import time
from typing import Dict, Tuple, Optional

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# ADMIN_CHAT_ID: isi dengan ID kamu (angka), contoh: 5504473114
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

# Cooldown anti spam (detik)
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "3"))

# Simpan mapping: pesan admin (message_id) -> (user_id, original_user_message_id)
# supaya saat admin reply, kita tahu harus kirim ke user yang mana.
ADMIN_MSG_MAP: Dict[int, Tuple[int, Optional[int]]] = {}

# Simpan last sent time per user
LAST_SENT: Dict[int, float] = {}


def require_env():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN belum di-set. Set ENV BOT_TOKEN dulu.")
    if ADMIN_CHAT_ID == 0:
        raise SystemExit("ADMIN_CHAT_ID belum di-set. Set ENV ADMIN_CHAT_ID (ID Telegram kamu).")


def now_ts() -> float:
    return time.time()


def cooldown_ok(user_id: int) -> bool:
    last = LAST_SENT.get(user_id, 0.0)
    return (now_ts() - last) >= COOLDOWN_SECONDS


def mark_sent(user_id: int):
    LAST_SENT[user_id] = now_ts()


def user_header(update: Update) -> str:
    u = update.effective_user
    if not u:
        return "Unknown User"
    name = (u.full_name or "User").replace("<", "").replace(">", "")
    username = f"@{u.username}" if u.username else "(no username)"
    return f"👤 {name} {username}\n🆔 <code>{u.id}</code>"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Kirim masukan kamu di sini: teks, foto, video, atau file.\n"
        "Nanti admin bakal bales lewat bot ini.\n\n"
        "Tips: kalau laporan bug, kirim screenshot + langkah reproduksi biar admin gak nangis."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Cara pakai:\n"
        "1) Kirim teks / foto / video / file\n"
        "2) Bot terusin ke admin\n"
        "3) Admin reply pesan itu → balasan nyampe ke kamu\n\n"
        "Perintah:\n"
        "/start /help"
    )


async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not update.effective_user:
        return

    user_id = update.effective_user.id

    if not cooldown_ok(user_id):
        await msg.reply_text("Pelan-pelan boss, jeda bentar ya. 😄")
        return

    mark_sent(user_id)

    header = user_header(update)
    caption = msg.caption or ""
    text = msg.text or ""

    # Kirim header dulu biar admin tahu konteks
    sent_header = await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=f"📩 <b>MASUKAN BARU</b>\n{header}",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )

    # Forward/copy konten user ke admin (biar admin bisa reply langsung)
    # Kita gunakan copy_message biar media/file aman dan rapi.
    sent_content = await context.bot.copy_message(
        chat_id=ADMIN_CHAT_ID,
        from_chat_id=msg.chat_id,
        message_id=msg.message_id,
        caption=caption if caption else None,
        parse_mode=ParseMode.HTML,
    )

    # Simpan mapping: admin_message_id -> user_id
    ADMIN_MSG_MAP[sent_content.message_id] = (user_id, msg.message_id)

    # Konfirmasi ke user
    await msg.reply_text("Sip, masukan kamu udah nyampe ke admin. Kalau dibales, bakal masuk ke sini.")


async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    # Pastikan hanya admin chat yang diproses
    if msg.chat_id != ADMIN_CHAT_ID:
        return

    # Harus reply ke pesan yang sebelumnya bot kirim/copy
    if not msg.reply_to_message:
        return

    replied_id = msg.reply_to_message.message_id
    target = ADMIN_MSG_MAP.get(replied_id)
    if not target:
        # Bukan reply ke konten user yang kita map
        return

    user_id, original_user_msg_id = target

    # Kirim balasan admin ke user
    # Kalau admin mengirim teks/media, kita copy juga biar fleksibel.
    try:
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=ADMIN_CHAT_ID,
            message_id=msg.message_id,
        )
    except Exception:
        # fallback: kalau copy gagal (jarang), minimal kirim teks
        if msg.text:
            await context.bot.send_message(chat_id=user_id, text=msg.text)

    # Info kecil ke admin (optional)
    await msg.reply_text("✅ Balasan terkirim ke user.")


def main():
    require_env()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))

    # Admin reply handler (lebih dulu supaya gak ketangkep handler user)
    app.add_handler(MessageHandler(filters.Chat(chat_id=ADMIN_CHAT_ID) & filters.REPLY, handle_admin_reply))

    # Semua pesan user (teks + media + dokumen)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_user_message))

    print("Feedback bot running...")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
