# src/analyzer.py

import re
from collections import Counter
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_all_videos, get_all_channels


def parse_duration(duration_str):
    if not duration_str:
        return 0
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
    if not match:
        return 0
    hours   = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds

def get_day_of_week(published_at):
    try:
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        return dt.strftime("%A")
    except:
        return "Unknown"


def analyze_best_days(videos):
    print("\n📅 Analyse des meilleurs jours de publication...")
    day_stats = {}
    for video in videos:
        day = get_day_of_week(video.get("published_at", ""))
        if day not in day_stats:
            day_stats[day] = {"day": day, "video_count": 0, "total_views": 0}
        day_stats[day]["video_count"] += 1
        day_stats[day]["total_views"] += video.get("view_count", 0)

    results = []
    for day, stats in day_stats.items():
        count = stats["video_count"]
        results.append({**stats, "avg_views": round(stats["total_views"] / count) if count else 0})
    results.sort(key=lambda x: x["avg_views"], reverse=True)
    print(f"  → Meilleur jour : {results[0]['day']} ({results[0]['avg_views']:,} vues en moyenne)")
    return results


def analyze_duration(videos):
    print("\n⏱️  Analyse de la durée idéale...")

    def get_duration_bucket(seconds):
        if seconds < 60:     return "< 1 min (Short)"
        elif seconds < 300:  return "1-5 min"
        elif seconds < 600:  return "5-10 min"
        elif seconds < 900:  return "10-15 min"
        elif seconds < 1800: return "15-30 min"
        else:                return "> 30 min"

    bucket_stats = {}
    for video in videos:
        bucket = get_duration_bucket(parse_duration(video.get("duration", "")))
        if bucket not in bucket_stats:
            bucket_stats[bucket] = {"bucket": bucket, "video_count": 0, "total_views": 0}
        bucket_stats[bucket]["video_count"] += 1
        bucket_stats[bucket]["total_views"] += video.get("view_count", 0)

    results = []
    for bucket, stats in bucket_stats.items():
        count = stats["video_count"]
        results.append({**stats, "avg_views": round(stats["total_views"] / count) if count else 0})
    results.sort(key=lambda x: x["avg_views"], reverse=True)
    print(f"  → Durée idéale : {results[0]['bucket']} ({results[0]['avg_views']:,} vues en moyenne)")
    return results


def analyze_title_keywords(videos, top_n=20):
    print("\n🏷️  Analyse des mots-clés dans les titres...")
    STOPWORDS = {
        "the", "a", "an", "in", "of", "to", "and", "is", "i", "my",
        "me", "for", "on", "at", "with", "this", "it", "be", "are",
        "was", "you", "your", "from", "that", "as", "or", "but",
        "so", "if", "no", "not", "we", "our", "he", "she", "they",
        "have", "has", "do", "did", "will", "can", "just", "how",
        "what", "when", "where", "why", "all", "by", "more", "up",
    }
    sorted_videos = sorted(videos, key=lambda x: x.get("view_count", 0), reverse=True)
    top_videos = sorted_videos[:max(1, len(sorted_videos) // 2)]

    word_counter = Counter()
    for video in top_videos:
        words = re.findall(r'\b[a-zA-Z]{3,}\b', video["title"].lower())
        word_counter.update([w for w in words if w not in STOPWORDS])

    results = [{"word": w, "count": c} for w, c in word_counter.most_common(top_n)]
    print(f"  → Top mots : {', '.join([r['word'] for r in results[:5]])}")
    return results


def run_analysis():
    """Lance toutes les analyses statistiques classiques."""
    videos   = get_all_videos()
    channels = get_all_channels()

    if not videos:
        print("❌ Aucune vidéo en base.")
        return None

    print(f"\n🎯 Analyse de {len(videos)} vidéos sur {len(channels)} chaînes...")

    return {
        "best_days": analyze_best_days(videos),
        "durations": analyze_duration(videos),
        "keywords":  analyze_title_keywords(videos),
        "total_videos":   len(videos),
        "total_channels": len(channels),
    }


if __name__ == "__main__":
    run_analysis()