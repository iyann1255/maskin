from telegram import InlineKeyboardButton, InlineKeyboardMarkup

CATEGORIES = [
    ("Bug", "BUG"),
    ("Saran Fitur", "FEATURE"),
    ("Laporan User", "REPORT"),
    ("Kerja Sama", "COLLAB"),
    ("Lainnya", "OTHER"),
]

CATEGORY_LABEL = {
    "BUG": "Bug",
    "FEATURE": "Saran Fitur",
    "REPORT": "Laporan User",
    "COLLAB": "Kerja Sama",
    "OTHER": "Lainnya",
}

def category_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for label, key in CATEGORIES:
        rows.append([InlineKeyboardButton(label, callback_data=f"cat:{key}")])
    rows.append([InlineKeyboardButton("Batal", callback_data="cat:CANCEL")])
    return InlineKeyboardMarkup(rows)

def safe_user_header(user) -> str:
    name = (user.full_name or "User").replace("<", "").replace(">", "")
    username = f"@{user.username}" if user.username else "(no username)"
    return f"👤 <b>{name}</b> {username}\n🆔 <code>{user.id}</code>"

def fmt_admin_post(header: str, category: str, desc: str, fid: int, dedup_of: int | None) -> str:
    extra = f"\n♻️ Duplicate of: <code>{dedup_of}</code>" if dedup_of else ""
    return (
        f"📩 <b>FEEDBACK MASUK</b>\n"
        f"{header}\n\n"
        f"🏷️ Category: <b>{category}</b>\n"
        f"🧾 ID: <code>{fid}</code>{extra}\n\n"
        f"📝 <b>Deskripsi</b>\n{desc}\n\n"
        f"↩️ Reply pesan ini untuk balas user."
    )

HELP_USER = (
    "Kirim masukan kamu lewat bot ini.\n\n"
    "Mulai cepat:\n"
    "• /new → bikin masukan (kategori + wizard)\n"
    "• /optout → berhenti menerima broadcast\n"
    "• /optin → aktifkan broadcast\n"
)

HELP_ADMIN = (
    "Admin panel:\n"
    "• /admins\n"
    "• /addadmin <id> (owner)\n"
    "• /deladmin <id> (owner)\n"
    "• /whitelist <id> [note]\n"
    "• /unwhitelist <id>\n"
    "• /note <feedback_id> <text>\n"
    "• /notes <feedback_id>\n"
    "• /exportcsv\n"
    "• /exportjson\n"
    "• /stats\n"
    "• /broadcast <text>\n"
)
