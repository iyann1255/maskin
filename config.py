import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Owner (superadmin) wajib
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# Optional: grup admin log (lebih enak kalau ada)
# contoh: -1001234567890
ADMIN_LOG_CHAT_ID = int(os.getenv("ADMIN_LOG_CHAT_ID", "0"))

# Anti-spam
RATE_WINDOW_SEC = int(os.getenv("RATE_WINDOW_SEC", "60"))
RATE_MAX_MSG = int(os.getenv("RATE_MAX_MSG", "6"))  # max user msg per window
AUTO_BLOCK_MINUTES = int(os.getenv("AUTO_BLOCK_MINUTES", "30"))

# Duplicate detection
DUP_WINDOW_HOURS = int(os.getenv("DUP_WINDOW_HOURS", "24"))

# Broadcast default: user auto opt-in setelah submit pertama
DEFAULT_OPT_IN = os.getenv("DEFAULT_OPT_IN", "true").lower() in ("1", "true", "yes", "y")

DB_PATH = os.getenv("DB_PATH", "feedback.sqlite3")
