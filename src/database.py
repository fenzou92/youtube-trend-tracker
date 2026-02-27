# src/database.py

import sqlite3
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def get_connection():
    """Retourne une connexion à la base SQLite."""
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─────────────────────────────────────────
# 1. CRÉATION DES TABLES
# ─────────────────────────────────────────

def init_db():
    """Crée les tables si elles n'existent pas."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            channel_id      TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            description     TEXT,
            subscriber_count INTEGER,
            video_count     INTEGER,
            view_count      INTEGER,
            country         TEXT,
            topic           TEXT,
            created_at      TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            video_id        TEXT PRIMARY KEY,
            channel_id      TEXT NOT NULL,
            title           TEXT NOT NULL,
            description     TEXT,
            published_at    TEXT,
            thumbnail       TEXT,
            view_count      INTEGER DEFAULT 0,
            like_count      INTEGER DEFAULT 0,
            comment_count   INTEGER DEFAULT 0,
            duration        TEXT,
            tags            TEXT,
            collected_at    TEXT,
            FOREIGN KEY (channel_id) REFERENCES channels(channel_id)
        )
    """)

    # ✅ NOUVEAU : table historique
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS video_stats_history (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id      TEXT NOT NULL,
            view_count    INTEGER,
            like_count    INTEGER,
            comment_count INTEGER,
            recorded_at   TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES videos(video_id)
        )
    """)

    conn.commit()
    conn.close()
    print("✅ Base de données initialisée")


# ─────────────────────────────────────────
# 2. INSERTION DES DONNÉES
# ─────────────────────────────────────────

def save_channels(channels):
    """Insère ou met à jour les chaînes en base."""
    conn = get_connection()
    cursor = conn.cursor()

    for channel in channels:
        cursor.execute("""
            INSERT INTO channels (
                channel_id, name, description, subscriber_count,
                video_count, view_count, country
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(channel_id) DO UPDATE SET
                subscriber_count = excluded.subscriber_count,
                video_count      = excluded.video_count,
                view_count       = excluded.view_count
        """, (
            channel["channel_id"],
            channel["name"],
            channel.get("description", ""),
            channel.get("subscriber_count", 0),
            channel.get("video_count", 0),
            channel.get("view_count", 0),
            channel.get("country", "N/A"),
        ))

    conn.commit()
    conn.close()
    print(f"✅ {len(channels)} chaînes sauvegardées")


def save_videos(videos):
    """Insère ou met à jour les vidéos + sauvegarde l'historique."""
    import json
    conn = get_connection()
    cursor = conn.cursor()

    for video in videos:
        cursor.execute("""
            INSERT INTO videos (
                video_id, channel_id, title, description,
                published_at, thumbnail, view_count, like_count,
                comment_count, duration, tags, collected_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                view_count    = excluded.view_count,
                like_count    = excluded.like_count,
                comment_count = excluded.comment_count,
                collected_at  = excluded.collected_at
        """, (
            video["video_id"],
            video["channel_id"],
            video["title"],
            video.get("description", ""),
            video.get("published_at", ""),
            video.get("thumbnail", ""),
            video.get("view_count", 0),
            video.get("like_count", 0),
            video.get("comment_count", 0),
            video.get("duration", ""),
            json.dumps(video.get("tags", [])),
            video.get("collected_at", ""),
        ))

    conn.commit()
    conn.close()
    print(f"✅ {len(videos)} vidéos sauvegardées")

    # ✅ NOUVEAU : snapshot historique automatique
    save_stats_history(videos)


# ✅ NOUVEAU : sauvegarde historique
def save_stats_history(videos):
    """Sauvegarde un snapshot des stats à chaque collecte."""
    conn = get_connection()
    cursor = conn.cursor()

    for video in videos:
        cursor.execute("""
            INSERT INTO video_stats_history 
                (video_id, view_count, like_count, comment_count)
            VALUES (?, ?, ?, ?)
        """, (
            video["video_id"],
            video.get("view_count", 0),
            video.get("like_count", 0),
            video.get("comment_count", 0),
        ))

    conn.commit()
    conn.close()
    print(f"📈 {len(videos)} snapshots historiques sauvegardés")


# ✅ NOUVEAU : récupère l'historique d'une vidéo
def get_video_history(video_id):
    """Retourne l'évolution des stats d'une vidéo dans le temps."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM video_stats_history
        WHERE video_id = ?
        ORDER BY recorded_at ASC
    """, (video_id,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


# ✅ NOUVEAU : vidéos en progression
def get_trending_videos(days=7):
    """Détecte les vidéos dont les vues ont le plus augmenté."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            h.video_id,
            v.title,
            c.name as channel_name,
            MIN(h.view_count) as views_start,
            MAX(h.view_count) as views_end,
            MAX(h.view_count) - MIN(h.view_count) as views_gained,
            COUNT(h.id) as snapshots
        FROM video_stats_history h
        JOIN videos v ON h.video_id = v.video_id
        JOIN channels c ON v.channel_id = c.channel_id
        WHERE h.recorded_at >= datetime('now', ?)
        GROUP BY h.video_id
        HAVING snapshots > 1
        ORDER BY views_gained DESC
        LIMIT 10
    """, (f'-{days} days',))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


# ─────────────────────────────────────────
# 3. LECTURE DES DONNÉES
# ─────────────────────────────────────────

def get_all_videos():
    """Retourne toutes les vidéos."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT v.*, c.name as channel_name, c.subscriber_count
        FROM videos v
        JOIN channels c ON v.channel_id = c.channel_id
        ORDER BY v.view_count DESC
    """)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_all_channels():
    """Retourne toutes les chaînes."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM channels ORDER BY subscriber_count DESC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_collection_history():
    """Affiche l'historique des collectes."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            DATE(recorded_at)  as date,
            COUNT(DISTINCT video_id) as videos_snapshot,
            MIN(recorded_at) as first_record,
            MAX(recorded_at) as last_record
        FROM video_stats_history
        GROUP BY DATE(recorded_at)
        ORDER BY date DESC
    """)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

# ─────────────────────────────────────────
# 4. MAIN
# ─────────────────────────────────────────

if __name__ == "__main__":
    init_db()

    from collector import collect_all  # ✅ utilise MAIN_THEME automatiquement
    channels, videos = collect_all()
    save_channels(channels)
    save_videos(videos)

    print(f"\n📦 En base : {len(get_all_channels())} chaînes, {len(get_all_videos())} vidéos")
    print("\n--- Top 3 vidéos ---")
    for v in get_all_videos()[:3]:
        print(f"  {v['title'][:50]} — {v['view_count']:,} vues")