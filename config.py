import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DB_PATH = os.getenv("DB_PATH", "taxi.db")
DRIVER_REG_CODE = os.getenv("DRIVER_REG_CODE", "taxi2024")

_admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = {
    int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip().isdigit()
}

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан. Скопируйте .env.example в .env и заполните.")
