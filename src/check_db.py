import sys
sys.path.insert(0, '.')
from database import get_all_videos, get_all_channels, get_collection_history

videos   = get_all_videos()
channels = get_all_channels()

print(f'📺 Chaînes en base : {len(channels)}')
print(f'🎬 Vidéos en base  : {len(videos)}')
print()
print('--- Chaînes ---')
for c in channels:
    print(f'  {c["name"][:40]:<40} {c["subscriber_count"]:>10,} abonnés')

print()
print('--- Historique des collectes ---')
for h in get_collection_history():
    print(f'  {h["date"]} → {h["videos_snapshot"]} vidéos snapshotées')