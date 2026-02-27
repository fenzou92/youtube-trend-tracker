# src/ml/topic_modeling.py

import os
import sys
import json
import pickle
import numpy as np
import pandas as pd
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import CountVectorizer

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR  = os.path.join(BASE_DIR, "src")
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, SRC_DIR)

from src.database import get_all_videos

MODEL_PATH = os.path.join(BASE_DIR, "models", "bertopic_model")


# ─────────────────────────────────────────
# 1. PRÉPARATION DES DONNÉES
# ─────────────────────────────────────────

def prepare_texts(videos):
    """
    Prépare les textes pour BERTopic.
    Combine titre + tags pour enrichir le contexte.
    """
    texts = []
    for video in videos:
        tags_str = ""
        try:
            tags = json.loads(video.get("tags", "[]"))
            tags_str = " ".join(tags[:10])  # max 10 tags
        except:
            pass
        text = f"{video['title']} {tags_str}".strip()
        texts.append(text)
    return texts


# ─────────────────────────────────────────
# 2. ENTRAÎNEMENT BERTOPIC
# ─────────────────────────────────────────

def train_bertopic(texts, nr_topics="auto"):
    """
    Entraîne BERTopic sur les titres de vidéos.
    Découvre automatiquement les sujets récurrents.
    """
    print("\n🧠 Entraînement de BERTopic...")
    print(f"  → {len(texts)} textes en entrée")

    # Modèle multilingue (japonais + anglais + français)
    print("  → Chargement du modèle sentence-transformers...")
    embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

    # Vectorizer pour de meilleurs mots-clés par topic
    vectorizer = CountVectorizer(
        ngram_range=(1, 2),
        stop_words=None,       # on garde tout, BERTopic gère
        min_df=1,
    )

    # BERTopic
    topic_model = BERTopic(
        embedding_model=embedding_model,
        vectorizer_model=vectorizer,
        nr_topics=nr_topics,   # "auto" ou un nombre fixe
        verbose=True,
        language="multilingual",
        min_topic_size=2,      # minimum 2 vidéos par topic (adapté à peu de données)
        calculate_probabilities=True,
    )

    topics, probs = topic_model.fit_transform(texts)

    print(f"\n✅ {len(set(topics)) - 1} topics découverts")  # -1 pour le topic -1 (outliers)
    return topic_model, topics, probs


# ─────────────────────────────────────────
# 3. AFFICHAGE DES TOPICS DÉCOUVERTS
# ─────────────────────────────────────────

def display_topics(topic_model):
    """Affiche un résumé des topics découverts."""
    print("\n📊 Topics découverts automatiquement :")
    print("-" * 60)

    topic_info = topic_model.get_topic_info()

    for _, row in topic_info.iterrows():
        if row["Topic"] == -1:
            continue  # ignore les outliers
        keywords = topic_model.get_topic(row["Topic"])
        kw_str = ", ".join([w for w, _ in keywords[:5]])
        print(f"  Topic {row['Topic']:2} | {row['Count']:3} vidéos | {kw_str}")

    return topic_info


# ─────────────────────────────────────────
# 4. ENRICHISSEMENT DES VIDÉOS
# ─────────────────────────────────────────

def enrich_videos_with_topics(videos, topic_model, topics, probs):
    """
    Ajoute le topic BERTopic à chaque vidéo.
    Retourne un DataFrame enrichi.
    """
    topic_info = topic_model.get_topic_info()

    # Crée un label lisible pour chaque topic
    topic_labels = {}
    for _, row in topic_info.iterrows():
        if row["Topic"] == -1:
            topic_labels[-1] = "other"
            continue
        keywords = topic_model.get_topic(row["Topic"])
        label = "_".join([w for w, _ in keywords[:2]])  # ex: "food_japan"
        topic_labels[row["Topic"]] = label

    enriched = []
    for i, video in enumerate(videos):
        topic_id = topics[i]
        confidence = float(max(probs[i])) if probs[i] is not None else 0.0

        enriched.append({
            **video,
            "bert_topic_id":    topic_id,
            "bert_topic_label": topic_labels.get(topic_id, "other"),
            "bert_confidence":  round(confidence, 3),
        })

    return pd.DataFrame(enriched)


# ─────────────────────────────────────────
# 5. ANALYSE DES PERFORMANCES PAR TOPIC
# ─────────────────────────────────────────

def analyze_topic_performance(df):
    """
    Calcule les vues moyennes, likes moyens par topic BERTopic.
    Permet d'identifier les sujets qui performent le mieux.
    """
    print("\n📈 Performance par topic découvert :")
    print("-" * 60)

    # Exclut les outliers
    df_filtered = df[df["bert_topic_id"] != -1].copy()

    stats = df_filtered.groupby("bert_topic_label").agg(
        video_count   = ("video_id",    "count"),
        avg_views     = ("view_count",  "mean"),
        avg_likes     = ("like_count",  "mean"),
        avg_comments  = ("comment_count", "mean"),
        avg_confidence= ("bert_confidence", "mean"),
    ).reset_index()

    stats["avg_views"]      = stats["avg_views"].astype(int)
    stats["avg_likes"]      = stats["avg_likes"].astype(int)
    stats["avg_confidence"] = stats["avg_confidence"].round(2)

    stats = stats.sort_values("avg_views", ascending=False)

    for _, row in stats.iterrows():
        print(f"  {row['bert_topic_label']:25} | "
              f"{row['video_count']:3} vidéos | "
              f"{row['avg_views']:>10,} vues moy. | "
              f"confiance: {row['avg_confidence']:.0%}")

    return stats


# ─────────────────────────────────────────
# 6. SAUVEGARDE / CHARGEMENT
# ─────────────────────────────────────────

def save_model(topic_model):
    """Sauvegarde le modèle BERTopic."""
    save_path = os.path.join(BASE_DIR, "models", "bertopic_model")
    
    # Supprime le dossier s'il existe déjà
    import shutil
    if os.path.exists(save_path):
        if os.path.isdir(save_path):
            shutil.rmtree(save_path)
        else:
            os.remove(save_path)
    
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    topic_model.save(save_path, serialization="safetensors", save_ctfidf=True)
    print(f"\n💾 Modèle sauvegardé → {save_path}")


def load_model():
    save_path = os.path.join(BASE_DIR, "models", "bertopic_model")
    if not os.path.exists(save_path):
        print("⚠️  Modèle introuvable, entraînement en cours...")
        return run_pipeline()
    print(f"📂 Chargement du modèle → {save_path}")
    return BERTopic.load(save_path)

# ─────────────────────────────────────────
# 7. PIPELINE COMPLET
# ─────────────────────────────────────────

def run_pipeline():
    """Lance le pipeline BERTopic complet."""
    videos = get_all_videos()
    if not videos:
        print("❌ Aucune vidéo en base.")
        return None, None

    texts = prepare_texts(videos)

    topic_model, topics, probs = train_bertopic(texts)
    display_topics(topic_model)

    df_enriched = enrich_videos_with_topics(videos, topic_model, topics, probs)
    stats = analyze_topic_performance(df_enriched)

    save_model(topic_model)

    return topic_model, df_enriched, stats


# ─────────────────────────────────────────
# TEST
# ─────────────────────────────────────────

if __name__ == "__main__":
    topic_model, df_enriched, stats = run_pipeline()

    if df_enriched is not None:
        print("\n🔮 Test sur de nouveaux titres :")
        print("-" * 60)
        test_titles = [
            "Morning routine in Tokyo | Living alone in Japan",
            "Best ramen restaurants in Osaka | Japanese food tour",
            "My apartment tour in Shibuya",
            "Traditional Japanese festival experience",
        ]
        predicted_topics, probs = topic_model.transform(test_titles)
        topic_info = topic_model.get_topic_info()

        for title, topic_id in zip(test_titles, predicted_topics):
            keywords = topic_model.get_topic(topic_id)
            kw_str = ", ".join([w for w, _ in keywords[:3]]) if keywords else "other"
            print(f"  📝 {title[:45]:<45}")
            print(f"     → Topic {topic_id} : {kw_str}\n")