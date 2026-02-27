# config.py
import os
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# ─────────────────────────────────────────
# THÈME PRINCIPAL — seule chose à changer
# ─────────────────────────────────────────
MAIN_THEME = "japan lifestyle"

# ─────────────────────────────────────────
# PARAMÈTRES DE COLLECTE
# ─────────────────────────────────────────
MAX_CHANNELS_PER_TOPIC = 15
MAX_VIDEOS_PER_CHANNEL = 50
DAYS_BACK = 180
MIN_SUBSCRIBERS = 5_000

# ─────────────────────────────────────────
# BASE DE DONNÉES
# ─────────────────────────────────────────
DB_PATH = "data/youtube_trends.db"