# src/ml/classifier.py

import json
import os
import sys
import pickle
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# Fix du path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR  = os.path.join(BASE_DIR, "src")
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, SRC_DIR)

from src.database import get_all_videos
import config

MODEL_PATH = os.path.join(BASE_DIR, "models", "topic_classifier.pkl")


# ─────────────────────────────────────────
# 1. PRÉPARATION DES DONNÉES
# ─────────────────────────────────────────

def prepare_training_data(videos):
    """
    Prépare les données d'entraînement à partir des vidéos.
    Utilise les règles de l'analyzer comme labels de départ (weak supervision).
    """
    from analyzer import detect_topic

    texts  = []
    labels = []

    for video in videos:
        # Combine titre + tags pour enrichir le texte
        tags_str = ""
        try:
            tags = json.loads(video.get("tags", "[]"))
            tags_str = " ".join(tags)
        except:
            pass

        text = f"{video['title']} {tags_str}".strip()
        label = detect_topic(video["title"], video.get("tags", "[]"))

        texts.append(text)
        labels.append(label)

    return texts, labels


# ─────────────────────────────────────────
# 2. ENTRAÎNEMENT DU MODÈLE TF-IDF + LR
# ─────────────────────────────────────────

def train_classifier(texts, labels):
    """
    Entraîne un pipeline TF-IDF + Logistic Regression.
    Simple, rapide, très lisible sur un portfolio.
    """
    print("\n🧠 Entraînement du classifieur NLP...")

    # Pipeline scikit-learn
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 2),   # unigrammes + bigrammes
            max_features=5000,
            sublinear_tf=True,    # lisse les fréquences
            strip_accents="unicode",
            analyzer="word",
            min_df=1,
        )),
        ("clf", LogisticRegression(
            max_iter=1000,
            C=1.0,
            class_weight="balanced",  # gère les classes déséquilibrées
        ))
    ])

    # Split train/test si assez de données
    unique_labels = list(set(labels))
    if len(texts) >= 20 and len(unique_labels) >= 2:
        X_train, X_test, y_train, y_test = train_test_split(
            texts, labels, test_size=0.2, random_state=42, stratify=labels
            if min([labels.count(l) for l in unique_labels]) >= 2 else None
        )
        pipeline.fit(X_train, y_train)

        print("\n📊 Évaluation sur le jeu de test :")
        y_pred = pipeline.predict(X_test)
        print(classification_report(y_test, y_pred, zero_division=0))
    else:
        # Pas assez de données → entraîne sur tout
        print("  ⚠️  Peu de données, entraînement sur tout le dataset")
        pipeline.fit(texts, labels)

    print("  ✅ Modèle entraîné")
    return pipeline


# ─────────────────────────────────────────
# 3. SAUVEGARDE / CHARGEMENT
# ─────────────────────────────────────────

def save_model(pipeline):
    """Sauvegarde le modèle entraîné."""
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(pipeline, f)
    print(f"  💾 Modèle sauvegardé → {MODEL_PATH}")


def load_model():
    """Charge le modèle depuis le disque."""
    if not os.path.exists(MODEL_PATH):
        print("  ⚠️  Modèle introuvable, entraînement en cours...")
        return train_and_save()
    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)


def train_and_save():
    """Pipeline complet : charge les données, entraîne et sauvegarde."""
    videos = get_all_videos()
    if not videos:
        print("❌ Aucune vidéo en base.")
        return None

    texts, labels = prepare_training_data(videos)
    pipeline = train_classifier(texts, labels)
    save_model(pipeline)
    return pipeline


# ─────────────────────────────────────────
# 4. PRÉDICTION
# ─────────────────────────────────────────

def predict_topic(title, tags=None, pipeline=None):
    """
    Prédit le sujet d'une vidéo à partir de son titre.
    Retourne le sujet + les probabilités par classe.
    """
    if pipeline is None:
        pipeline = load_model()

    tags_str = " ".join(tags) if tags else ""
    text = f"{title} {tags_str}".strip()

    predicted  = pipeline.predict([text])[0]
    proba      = pipeline.predict_proba([text])[0]
    classes    = pipeline.classes_

    proba_dict = {cls: round(float(p), 3) for cls, p in zip(classes, proba)}
    confidence = round(float(max(proba)), 3)

    return {
        "title":      title,
        "topic":      predicted,
        "confidence": confidence,
        "probabilities": proba_dict,
    }


def predict_all_videos(pipeline=None):
    """
    Prédit le sujet de toutes les vidéos en base.
    Retourne les vidéos enrichies avec leur topic ML.
    """
    if pipeline is None:
        pipeline = load_model()

    videos = get_all_videos()
    results = []

    for video in videos:
        prediction = predict_topic(video["title"], pipeline=pipeline)
        results.append({
            **video,
            "ml_topic":      prediction["topic"],
            "ml_confidence": prediction["confidence"],
        })

    return results


# ─────────────────────────────────────────
# 5. ANALYSE DES TOPICS ML
# ─────────────────────────────────────────

def analyze_ml_topics(videos_with_predictions):
    """
    Compare les performances des sujets détectés par le ML.
    """
    print("\n📊 Analyse des topics ML...")

    topic_stats = {}

    for video in videos_with_predictions:
        topic = video["ml_topic"]
        if topic not in topic_stats:
            topic_stats[topic] = {
                "topic": topic,
                "video_count": 0,
                "total_views": 0,
                "avg_confidence": 0,
            }
        topic_stats[topic]["video_count"] += 1
        topic_stats[topic]["total_views"] += video.get("view_count", 0)
        topic_stats[topic]["avg_confidence"] += video.get("ml_confidence", 0)

    results = []
    for topic, stats in topic_stats.items():
        count = stats["video_count"]
        results.append({
            **stats,
            "avg_views":      round(stats["total_views"] / count) if count else 0,
            "avg_confidence": round(stats["avg_confidence"] / count, 2) if count else 0,
        })

    results.sort(key=lambda x: x["avg_views"], reverse=True)
    return results


# ─────────────────────────────────────────
# TEST
# ─────────────────────────────────────────

if __name__ == "__main__":
    # Entraîne et sauvegarde le modèle
    pipeline = train_and_save()

    if pipeline:
        # Test sur quelques titres
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
            result = predict_topic(title, pipeline=pipeline)
            print(f"  📝 {title[:45]:<45}")
            print(f"     → {result['topic']:12} (confiance: {result['confidence']:.0%})")
            print()

        # Analyse globale
        videos_predicted = predict_all_videos(pipeline)
        ml_topics = analyze_ml_topics(videos_predicted)

        print("\n📈 Performance par topic ML :")
        print("-" * 60)
        for t in ml_topics:
            print(f"  {t['topic']:12} | {t['video_count']:3} vidéos | "
                  f"{t['avg_views']:>10,} vues moy. | "
                  f"confiance: {t['avg_confidence']:.0%}")