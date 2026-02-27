# src/ml/topic_generator.py

ANGLES = [
    "vlog", "daily life", "morning routine", "food tour",
    "apartment tour", "culture", "living in", "vie au",
    "travel", "street food", "moving to", "expat"
]

def generate_search_topics(main_theme, n_topics=8):
    """Génère des topics de recherche dynamiquement."""
    topics = []
    for angle in ANGLES[:n_topics]:
        if angle in ["living in", "vie au", "moving to"]:
            topics.append(f"{angle} {main_theme}")
        else:
            topics.append(f"{main_theme} {angle}")
    return topics