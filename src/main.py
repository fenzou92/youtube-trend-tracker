# src/main.py

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db, save_channels, save_videos, get_all_videos
from collector import collect_all
from analyzer import run_analysis
from ml.topic_modeling import run_pipeline

def main():
    print("🚀 Lancement du pipeline complet...\n")

    # 1. Collecte
    print("="*50)
    print("📡 ÉTAPE 1 : Collecte des données YouTube")
    print("="*50)
    init_db()
    channels, videos = collect_all()
    save_channels(channels)
    save_videos(videos)

    # 2. Analyse classique
    print("\n" + "="*50)
    print("📊 ÉTAPE 2 : Analyse statistique")
    print("="*50)
    run_analysis()

    # 3. Topic modeling ML
    print("\n" + "="*50)
    print("🧠 ÉTAPE 3 : Topic Modeling BERTopic")
    print("="*50)
    run_pipeline()

    print("\n✅ Pipeline terminé ! Lance le dashboard avec :")
    print("   streamlit run dashboard.py")

if __name__ == "__main__":
    main()