# src/collector.py

from googleapiclient.discovery import build
from datetime import datetime, timedelta, timezone 
import sys
import os

# Ajoute le dossier parent au path pour importer config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def get_youtube_client():
    """Crée et retourne un client YouTube API."""
    return build("youtube", "v3", developerKey=config.YOUTUBE_API_KEY)


# ─────────────────────────────────────────
# 1. RECHERCHE DE CHAÎNES PAR SUJET
# ─────────────────────────────────────────

def search_channels_by_topic(youtube, topic, max_results=None):
    """
    Recherche des chaînes YouTube par mot-clé.
    Retourne une liste de chaînes avec leurs infos de base.
    """
    if max_results is None:
        max_results = config.MAX_CHANNELS_PER_TOPIC

    print(f"\n🔍 Recherche de chaînes pour le sujet : '{topic}'")

    request = youtube.search().list(
        part="snippet",
        q=topic,
        type="channel",
        maxResults=max_results,
        relevanceLanguage="en",
        order="relevance"
    )
    response = request.execute()

    channels = []
    for item in response.get("items", []):
        channel = {
            "channel_id": item["snippet"]["channelId"],
            "name": item["snippet"]["title"],
            "description": item["snippet"]["description"],
            "topic": topic,
        }
        channels.append(channel)
        print(f"  ✅ Trouvé : {channel['name']} ({channel['channel_id']})")

    return channels


# ─────────────────────────────────────────
# 2. DÉTAILS D'UNE CHAÎNE (abonnés, etc.)
# ─────────────────────────────────────────

def get_channel_details(youtube, channel_ids):
    """
    Récupère les détails d'une liste de chaînes :
    abonnés, nombre de vidéos, vues totales.
    Filtre les chaînes sous le seuil MIN_SUBSCRIBERS.
    """
    print(f"\n📊 Récupération des détails pour {len(channel_ids)} chaînes...")

    request = youtube.channels().list(
        part="snippet,statistics",
        id=",".join(channel_ids)
    )
    response = request.execute()

    channels = []
    for item in response.get("items", []):
        stats = item.get("statistics", {})
        subscriber_count = int(stats.get("subscriberCount", 0))

        # Filtre les petites chaînes
        if subscriber_count < config.MIN_SUBSCRIBERS:
            print(f"  ⏭️  Ignoré (trop peu d'abonnés) : {item['snippet']['title']}")
            continue

        channel = {
            "channel_id": item["id"],
            "name": item["snippet"]["title"],
            "description": item["snippet"]["description"],
            "subscriber_count": subscriber_count,
            "video_count": int(stats.get("videoCount", 0)),
            "view_count": int(stats.get("viewCount", 0)),
            "country": item["snippet"].get("country", "N/A"),
        }
        channels.append(channel)
        print(f"  ✅ {channel['name']} — {channel['subscriber_count']:,} abonnés")

    return channels


# ─────────────────────────────────────────
# 3. VIDÉOS D'UNE CHAÎNE
# ─────────────────────────────────────────

def get_channel_videos(youtube, channel_id, channel_name):
    """
    Récupère les dernières vidéos d'une chaîne
    sur la période définie dans config.DAYS_BACK.
    """
    print(f"\n🎬 Récupération des vidéos de : {channel_name}")

    # Date limite (ex: 90 jours en arrière)
    published_after = (
        datetime.now(timezone.utc) - timedelta(days=config.DAYS_BACK)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    request = youtube.search().list(
        part="snippet",
        channelId=channel_id,
        type="video",
        order="date",
        maxResults=config.MAX_VIDEOS_PER_CHANNEL,
        publishedAfter=published_after
    )
    response = request.execute()

    video_ids = []
    videos_basic = []

    for item in response.get("items", []):
        video_id = item["id"]["videoId"]
        video_ids.append(video_id)
        videos_basic.append({
            "video_id": video_id,
            "channel_id": channel_id,
            "title": item["snippet"]["title"],
            "published_at": item["snippet"]["publishedAt"],
            "thumbnail": item["snippet"]["thumbnails"]["high"]["url"],
        })

    print(f"  → {len(video_ids)} vidéos trouvées")
    return video_ids, videos_basic


# ─────────────────────────────────────────
# 4. STATS DÉTAILLÉES DES VIDÉOS
# ─────────────────────────────────────────

def get_videos_stats(youtube, video_ids, videos_basic):
    """
    Enrichit les vidéos avec leurs statistiques détaillées :
    vues, likes, commentaires, durée, tags.
    """
    if not video_ids:
        return []

    # L'API accepte max 50 IDs par appel
    request = youtube.videos().list(
        part="statistics,contentDetails,snippet",
        id=",".join(video_ids[:50])
    )
    response = request.execute()

    # Crée un dict pour merger les données
    stats_map = {item["id"]: item for item in response.get("items", [])}

    videos_enriched = []
    for video in videos_basic:
        vid_id = video["video_id"]
        data = stats_map.get(vid_id, {})
        stats = data.get("statistics", {})
        snippet = data.get("snippet", {})

        video_enriched = {
            **video,
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
            "duration": data.get("contentDetails", {}).get("duration", ""),
            "tags": snippet.get("tags", []),
            "description": snippet.get("description", "")[:500],
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }
        videos_enriched.append(video_enriched)

    return videos_enriched


# ─────────────────────────────────────────
# 5. PIPELINE COMPLET
# ─────────────────────────────────────────

def collect_all(topics=None):
    """
    Pipeline principal :
    Pour chaque sujet → trouve les chaînes → récupère leurs vidéos → retourne tout.
    """
    if topics is None:
        topics = config.SEARCH_TOPICS

    youtube = get_youtube_client()
    all_channels = []
    all_videos = []

    for topic in topics:
        # Étape 1 : cherche les chaînes
        channels_raw = search_channels_by_topic(youtube, topic)
        channel_ids = [c["channel_id"] for c in channels_raw]

        # Étape 2 : récupère leurs détails + filtre
        channels_detailed = get_channel_details(youtube, channel_ids)
        all_channels.extend(channels_detailed)

        # Étape 3 : récupère les vidéos de chaque chaîne
        for channel in channels_detailed:
            video_ids, videos_basic = get_channel_videos(
                youtube, channel["channel_id"], channel["name"]
            )
            # Étape 4 : enrichit avec les stats
            videos_enriched = get_videos_stats(youtube, video_ids, videos_basic)
            all_videos.extend(videos_enriched)

    print(f"\n✅ Collecte terminée : {len(all_channels)} chaînes, {len(all_videos)} vidéos")
    return all_channels, all_videos


# ─────────────────────────────────────────
# TEST RAPIDE
# ─────────────────────────────────────────

if __name__ == "__main__":
    channels, videos = collect_all(topics=["japan lifestyle vlog"])

    print("\n--- Aperçu des chaînes ---")
    for c in channels[:3]:
        print(f"  {c['name']} — {c['subscriber_count']:,} abonnés")

    print("\n--- Aperçu des vidéos ---")
    for v in videos[:3]:
        print(f"  {v['title']} — {v['view_count']:,} vues")