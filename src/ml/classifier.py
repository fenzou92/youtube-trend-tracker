# src/ml/classifier.py

import json
import os
import sys
import pickle
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from sentence_transformers import SentenceTransformer

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR  = os.path.join(BASE_DIR, "src")
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, SRC_DIR)

from src.database import get_all_videos
import config

MODEL_PATH     = os.path.join(BASE_DIR, "models", "topic_classifier.pkl")
EMBEDDER_NAME  = "all-MiniLM-L6-v2"  # léger, rapide, très bon


# ─────────────────────────────────────────
# 1. EMBEDDINGS
# ─────────────────────────────────────────

def get_embedder():
    """Charge le modèle sentence-transformers."""
    print("  📥 Chargement du modèle d'embeddings...")
    return SentenceTransformer(EMBEDDER_NAME)


def embed_texts(texts, embedder=None):
    """
    Convertit une liste de textes en vecteurs numériques.
    Ces vecteurs capturent le sens sémantique des phrases.
    """
    if embedder is None:
        embedder = get_embedder()
    print(f"  🔢 Création des embeddings pour {len(texts)} textes...")
    embeddings = embedder.encode(texts, show_progress_bar=True)
    return embeddings


# ─────────────────────────────────────────
# 2. PRÉPARATION DES DONNÉES
# ─────────────────────────────────────────

def prepare_training_data(videos):
    """
    Prépare les données d'entraînement.
    Utilise les règles de l'analyzer comme labels (weak supervision).
    """
    from src.analyzer import detect_topic

    texts  = []
    labels = []

    for video in videos:
        tags_str = ""
        try:
            tags = json.loads(video.get("tags", "[]"))
            tags_str = " ".join(tags)
        except:
            pass

        text  = f"{video['title']} {tags_str}".strip()
        label = detect_topic(video["title"], video.get("tags", "[]"))

        texts.append(text)
        labels.append(label)

    # Résumé des labels
    from collections import Counter
    label_counts = Counter(labels)
    print(f"\n  📊 Distribution des labels :")
    for label, count in label_counts.most_common():
        print(f"     {label:12} → {count} vidéos")

    return texts, labels


# ─────────────────────────────────────────
# 3. ENTRAÎNEMENT
# ─────────────────────────────────────────

def train_classifier(texts, labels):
    """
    Entraîne un classifieur Logistic Regression
    sur les embeddings sémantiques.
    """
    print("\n🧠 Entraînement du classifieur sémantique...")

    embedder   = get_embedder()
    embeddings = embed_texts(texts, embedder)

    unique_labels = list(set(labels))
    min_class_count = min([labels.count(l) for l in unique_labels])

    clf = LogisticRegression(
        max_iter=1000,
        C=1.0,
        class_weight="balanced",
    )

    if len(texts) >= 20 and len(unique_labels) >= 2 and min_class_count >= 2:
        X_train, X_test, y_train, y_test = train_test_split(
            embeddings, labels,
            test_size=0.2,
            random_state=42,
            stratify=labels
        )
        clf.fit(X_train, y_train)

        print("\n📊 Évaluation sur le jeu de test :")
        y_pred = clf.predict(X_test)
        print(classification_report(y_test, y_pred, zero_division=0))
    else:
        print("  ⚠️  Entraînement sur tout le dataset (peu de données)")
        clf.fit(embeddings, labels)

    # Sauvegarde embedder + clf ensemble
    model = {"embedder_name": EMBEDDER_NAME, "clf": clf}
    print("  ✅ Modèle entraîné")
    return model


# ─────────────────────────────────────────
# 4. SAUVEGARDE / CHARGEMENT
# ─────────────────────────────────────────

def save_model(model):
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    print(f"  💾 Modèle sauvegardé → {MODEL_PATH}")


def load_model():
    if not os.path.exists(MODEL_PATH):
        print("  ⚠️  Modèle introuvable, entraînement en cours...")
        return train_and_save()
    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)


def train_and_save():
    videos = get_all_videos()
    if not videos:
        print("❌ Aucune vidéo en base.")
        return None
    texts, labels = prepare_training_data(videos)
    model = train_classifier(texts, labels)
    save_model(model)
    return model


# ─────────────────────────────────────────
# 5. PRÉDICTION
# ─────────────────────────────────────────

def predict_topic(title, tags=None, model=None):
    """
    Prédit le sujet d'une vidéo à partir de son titre.
    """
    if model is None:
        model = load_model()

    embedder = SentenceTransformer(model["embedder_name"])
    clf      = model["clf"]

    tags_str  = " ".join(tags) if tags else ""
    text      = f"{title} {tags_str}".strip()
    embedding = embedder.encode([text])

    predicted = clf.predict(embedding)[0]
    proba     = clf.predict_proba(embedding)[0]
    classes   = clf.classes_

    proba_dict = {cls: round(float(p), 3) for cls, p in zip(classes, proba)}
    confidence = round(float(max(proba)), 3)

    return {
        "title":         title,
        "topic":         predicted,
        "confidence":    confidence,
        "probabilities": proba_dict,
    }


def predict_all_videos(model=None):
    """Prédit le sujet de toutes les vidéos en base."""
    if model is None:
        model = load_model()

    embedder = SentenceTransformer(model["embedder_name"])
    clf      = model["clf"]
    videos   = get_all_videos()

    # Encode toutes les vidéos en une seule fois (plus rapide)
    texts = [v["title"] for v in videos]
    embeddings = embedder.encode(texts, show_progress_bar=True)

    predictions = clf.predict(embeddings)
    probas      = clf.predict_proba(embeddings)

    results = []
    for video, pred, proba in zip(videos, predictions, probas):
        results.append({
            **video,
            "ml_topic":      pred,
            "ml_confidence": round(float(max(proba)), 3),
        })

    return results


def analyze_ml_topics(videos_with_predictions):
    """Analyse les performances par topic ML."""
    topic_stats = {}

    for video in videos_with_predictions:
        topic = video["ml_topic"]
        if topic not in topic_stats:
            topic_stats[topic] = {
                "topic": topic,
                "video_count": 0,
                "total_views": 0,
                "total_confidence": 0,
            }
        topic_stats[topic]["video_count"]      += 1
        topic_stats[topic]["total_views"]      += video.get("view_count", 0)
        topic_stats[topic]["total_confidence"] += video.get("ml_confidence", 0)

    results = []
    for topic, stats in topic_stats.items():
        count = stats["video_count"]
        results.append({
            **stats,
            "avg_views":      round(stats["total_views"] / count) if count else 0,
            "avg_confidence": round(stats["total_confidence"] / count, 2) if count else 0,
        })

    results.sort(key=lambda x: x["avg_views"], reverse=True)
    return results


# ─────────────────────────────────────────
# TEST
# ─────────────────────────────────────────

if __name__ == "__main__":
    model = train_and_save()

    if model:
        test_titles = [
            "Morning routine in Tokyo | Living alone in Japan",
            "Best ramen restaurants in Osaka | Japanese food tour",
            "My apartment tour in Shibuya | Japan vlog",
            "Traditional Japanese festival experience",
            "Weekly grocery shopping in Japan",
        ]

        print("\n🔮 Tests de prédiction :")
        print("-" * 60)
        for title in test_titles:
            result = predict_topic(title, model=model)
            print(f"  📝 {title[:45]:<45}")
            print(f"     → {result['topic']:12} (confiance: {result['confidence']:.0%})")
            print()

        videos_predicted = predict_all_videos(model)
        ml_topics = analyze_ml_topics(videos_predicted)

        print("\n📈 Performance par topic ML :")
        print("-" * 60)
        for t in ml_topics:
            print(f"  {t['topic']:12} | {t['video_count']:3} vidéos | "
                  f"{t['avg_views']:>10,} vues moy. | "
                  f"confiance: {t['avg_confidence']:.0%}")