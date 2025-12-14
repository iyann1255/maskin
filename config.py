import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "8501985808:AAGAAVdF7zaU1bzYjtmsH64irc0Mh99ieWk").strip()

# Owner (superadmin) wajib
OWNER_ID = int(os.getenv("OWNER_ID", "5504473114"))

# Optional: grup admin log (disarankan)
# contoh: -1001234567890
ADMIN_LOG_CHAT_ID = int(os.getenv("ADMIN_LOG_CHAT_ID", "0"))

# Anti-spam ringan (RATE LIMIT) - bisa dimatikan
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("1", "true", "yes", "y")
RATE_WINDOW_SEC = int(os.getenv("RATE_WINDOW_SEC", "60"))
RATE_MAX_MSG = int(os.getenv("RATE_MAX_MSG", "8"))  # max user msg per window

# Duplicate detection (jam)
DUP_WINDOW_HOURS = int(os.getenv("DUP_WINDOW_HOURS", "24"))

# Broadcast default: user auto opt-in setelah pertama kali submit
DEFAULT_OPT_IN = os.getenv("DEFAULT_OPT_IN", "true").lower() in ("1", "true", "yes", "y")

DB_PATH = os.getenv("DB_PATH", "feedback.sqlite3")
