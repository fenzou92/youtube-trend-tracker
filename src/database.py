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
    conn.row_factory = sqlite3.Row  # permet d'accéder aux colonnes par nom
    return conn


# ─────────────────────────────────────────
# 1. CRÉATION DES TABLES
# ─────────────────────────────────────────

def init_db():
    """Crée les tables si elles n'existent pas."""
    conn = get_connection()
    cursor = conn.cursor()

    # Table des chaînes
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

    # Table des vidéos
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
            tags            TEXT,  -- stocké en JSON
            collected_at    TEXT,
            FOREIGN KEY (channel_id) REFERENCES channels(channel_id)
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
    """Insère ou met à jour les vidéos en base."""
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


# ─────────────────────────────────────────
# 3. LECTURE DES DONNÉES
# ─────────────────────────────────────────

def get_all_videos():
    """Retourne toutes les vidéos sous forme de liste de dicts."""
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


# ─────────────────────────────────────────
# 4. TEST
# ─────────────────────────────────────────

if __name__ == "__main__":
    # Initialise la BDD
    init_db()

    # Test avec le collector
    from collector import collect_all

    channels, videos = collect_all(topics=["japan lifestyle vlog"])
    save_channels(channels)
    save_videos(videos)

    # Vérifie ce qui est en base
    print(f"\n📦 En base : {len(get_all_channels())} chaînes, {len(get_all_videos())} vidéos")

    print("\n--- Top 3 vidéos ---")
    for v in get_all_videos()[:3]:
        print(f"  {v['title'][:50]} — {v['view_count']:,} vues")