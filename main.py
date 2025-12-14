import os
import time
from typing import Dict, Tuple, Optional, List

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8501985808:AAGAAVdF7zaU1bzYjtmsH64irc0Mh99ieWk").strip()

# Banyak admin: pisahkan dengan koma
# Contoh: "5504473114,123456789,-1009876543210"
# Bisa user ID admin (angka positif) atau grup/admin log (chat id negatif)
ADMIN_CHAT_IDS_RAW = os.getenv("ADMIN_CHAT_IDS", "").strip()

COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "3"))

# Map per admin chat:
# key: (admin_chat_id, admin_message_id_yang_di-reply) -> (user_id, original_user_message_id)
ADMIN_MSG_MAP: Dict[Tuple[int, int], Tuple[int, Optional[int]]] = {}

# Anti spam ringan per user
LAST_SENT: Dict[int, float] = {}


def require_env():
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN belum di-set. Set ENV BOT_TOKEN dulu.")
    if not ADMIN_CHAT_IDS_RAW:
        raise SystemExit("ADMIN_CHAT_IDS belum di-set. Set ENV ADMIN_CHAT_IDS (pisah koma).")


def parse_admin_chats(raw: str) -> List[int]:
    out: List[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            raise SystemExit(f"ADMIN_CHAT_IDS berisi value tidak valid: {part}")
    if not out:
        raise SystemExit("ADMIN_CHAT_IDS kosong / tidak valid.")
    return out


ADMIN_CHAT_IDS = parse_admin_chats(ADMIN_CHAT_IDS_RAW)


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


def admin_tag() -> str:
    # Biar admin tahu cara bales
    return "↩️ Reply pesan ini untuk balas user."


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Kirim masukan kamu di sini: teks, foto, video, atau file.\n"
        "Nanti admin bakal bales lewat bot ini."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Cara pakai:\n"
        "1) Kirim teks / foto / video / file\n"
        "2) Bot terusin ke admin (multi-admin)\n"
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
        await msg.reply_text("Pelan-pelan boss, jeda bentar ya.")
        return

    mark_sent(user_id)

    header = user_header(update)
    caption = msg.caption or ""

    # Kirim ke semua admin chat
    for admin_chat_id in ADMIN_CHAT_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_chat_id,
                text=f"📩 <b>MASUKAN BARU</b>\n{header}\n\n{admin_tag()}",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )

            sent_content = await context.bot.copy_message(
                chat_id=admin_chat_id,
                from_chat_id=msg.chat_id,
                message_id=msg.message_id,
                caption=caption if caption else None,
                parse_mode=ParseMode.HTML,
            )

            # Simpan mapping spesifik admin chat + message id
            ADMIN_MSG_MAP[(admin_chat_id, sent_content.message_id)] = (user_id, msg.message_id)

        except Exception as e:
            # Jangan bikin user nunggu; log saja di stdout
            print(f"[WARN] gagal kirim ke admin_chat_id={admin_chat_id}: {e}")

    await msg.reply_text("Sip, masukan kamu udah terkirim ke admin. Nanti kalau dibales, masuk ke sini.")


async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    admin_chat_id = msg.chat_id

    # Pastikan chat ini termasuk daftar admin
    if admin_chat_id not in ADMIN_CHAT_IDS:
        return

    # Harus reply
    if not msg.reply_to_message:
        return

    replied_msg_id = msg.reply_to_message.message_id
    target = ADMIN_MSG_MAP.get((admin_chat_id, replied_msg_id))
    if not target:
        return

    user_id, _original_user_msg_id = target

    # Relay balasan admin ke user (teks/media/file)
    try:
        await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=admin_chat_id,
            message_id=msg.message_id,
        )
        await msg.reply_text("✅ Balasan terkirim ke user.")
    except Exception as e:
        print(f"[ERROR] gagal kirim balasan ke user {user_id}: {e}")
        if msg.text:
            try:
                await context.bot.send_message(chat_id=user_id, text=msg.text)
                await msg.reply_text("✅ Balasan teks terkirim ke user (fallback).")
            except Exception as e2:
                print(f"[ERROR] fallback juga gagal: {e2}")


def main():
    require_env()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))

    # Admin reply handler
    # Kita pakai filters.REPLY dan biarkan handler sendiri yang cek chat_id admin.
    app.add_handler(MessageHandler(filters.REPLY & ~filters.COMMAND, handle_admin_reply))

    # Semua pesan user (teks + media + dokumen)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_user_message))

    print("Feedback bot (multi-admin) running...")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
