import os

# Saari configurations bina kisi hardcode value ke Render Environment Variables se fetch hongi
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID")
LOG_CHANNEL = os.environ.get("LOG_CHANNEL")
VERIFY_EXPIRE_HOURS = os.environ.get("VERIFY_EXPIRE_HOURS")
SHORTENER_URL = os.environ.get("SHORTENER_URL")
SHORTENER_API = os.environ.get("SHORTENER_API")
HOW_TO_VERIFY_LINK = os.environ.get("HOW_TO_VERIFY_LINK")
DISKWALA_PROXY_URL = os.environ.get("DISKWALA_PROXY_URL")
DISKWALA_API_KEY = os.environ.get("DISKWALA_API_KEY")

# Public aur Private Force Channels ke liye alag variables (Agar khali ho ya 'false' ho toh disable rahenge)
public_raw = os.environ.get("PUBLIC_FORCE_CHANNELS", "").strip()
if public_raw.lower() in ["false", "none", "off", ""]:
    PUBLIC_CHANNELS = []
else:
    PUBLIC_CHANNELS = [ch.strip() for ch in public_raw.split(",") if ch.strip()]

private_raw = os.environ.get("PRIVATE_FORCE_CHANNELS", "").strip()
if private_raw.lower() in ["false", "none", "off", ""]:
    PRIVATE_CHANNELS = []
else:
    PRIVATE_CHANNELS = [ch.strip() for ch in private_raw.split(",") if ch.strip()]

# Check which keys are missing or unconfigured
missing_keys = []
config_dict = {
    "API_ID": API_ID,
    "API_HASH": API_HASH,
    "BOT_TOKEN": BOT_TOKEN,
    "ADMIN_ID": ADMIN_ID,
    "LOG_CHANNEL": LOG_CHANNEL,
    "VERIFY_EXPIRE_HOURS": VERIFY_EXPIRE_HOURS,
    "SHORTENER_URL": SHORTENER_URL,
    "SHORTENER_API": SHORTENER_API
    "DISKWALA_PROXY_URL": DISKWALA_PROXY_URL,
    "DISKWALA_API_KEY": DISKWALA_API_KEY   
}

for key, value in config_dict.items():
    if not value:
        missing_keys.append(key)

# Safe type conversions with fallbacks so bot never crashes on missing keys
API_ID = int(API_ID) if API_ID and API_ID.isdigit() else 0
ADMIN_ID = int(ADMIN_ID) if ADMIN_ID and ADMIN_ID.isdigit() else 0
LOG_CHANNEL = int(LOG_CHANNEL) if LOG_CHANNEL else 0
VERIFY_EXPIRE_HOURS = int(VERIFY_EXPIRE_HOURS) if VERIFY_EXPIRE_HOURS and VERIFY_EXPIRE_HOURS.isdigit() else 12
