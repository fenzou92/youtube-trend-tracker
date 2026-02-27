# config.py revu
import os
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Plus de liste fixe ! On recherche par sujet
SEARCH_TOPICS = [
    "japan lifestyle vlog",
    "vie au japon",
    "living in japan",
    "japan daily life",
]

# Paramètres
MAX_CHANNELS_PER_TOPIC = 10   # nb de chaînes à récupérer par sujet
MAX_VIDEOS_PER_CHANNEL = 30   # nb de vidéos à analyser par chaîne
DAYS_BACK = 90                 # fenêtre d'analyse

# Seuil minimum d'abonnés pour filtrer les petites chaînes
MIN_SUBSCRIBERS = 10_000

DB_PATH = "data/youtube_trends.db"

TOPICS_KEYWORDS = {
    "routine": ["routine", "morning", "evening", "daily"],
    "voyage": ["travel", "trip", "vlog", "voyage"],
    "food": ["food", "restaurant", "eat", "cuisine", "ramen"],
    "culture": ["culture", "tradition", "festival", "temple"],
    "logement": ["apartment", "house", "room", "appartement"],
}
