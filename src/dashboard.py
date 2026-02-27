# src/dashboard.py

import streamlit as st
import plotly.express as px
import pandas as pd
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analyzer import run_analysis
from database import get_all_videos, get_all_channels
from ml.topic_modeling import run_pipeline, load_model, enrich_videos_with_topics, analyze_topic_performance

# ─────────────────────────────────────────
# CONFIG PAGE
# ─────────────────────────────────────────

st.set_page_config(
    page_title="🎌 YouTube Japan Trend Tracker",
    page_icon="🎌",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────

with st.sidebar:
    st.title("🎌 Japan Trend Tracker")
    st.markdown("---")
    st.markdown("### Filtres")
    channels = get_all_channels()
    channel_names = ["Toutes"] + [c["name"] for c in channels]
    selected_channel = st.selectbox("📺 Chaîne", channel_names)
    st.markdown("---")
    st.markdown("### À propos")
    st.info("Données collectées via YouTube Data API v3\nTopics découverts via BERTopic ML")

# ─────────────────────────────────────────
# CHARGEMENT DES DONNÉES
# ─────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_data():
    videos   = get_all_videos()
    channels = get_all_channels()
    results  = run_analysis()
    return videos, channels, results

@st.cache_data(ttl=3600)
def load_ml_data():
    try:
        topic_model = load_model()
        videos = get_all_videos()
        texts = [v["title"] for v in videos]
        topics, probs = topic_model.transform(texts)
        df_enriched = enrich_videos_with_topics(videos, topic_model, topics, probs)
        ml_stats = analyze_topic_performance(df_enriched)
        return df_enriched, ml_stats
    except Exception as e:
        st.warning(f"⚠️ Modèle BERTopic non disponible : {e}")
        return None, None

with st.spinner("Chargement des données..."):
    videos, channels, results = load_data()
    df_enriched, ml_stats = load_ml_data()

if selected_channel != "Toutes":
    videos = [v for v in videos if v["channel_name"] == selected_channel]

df_videos   = pd.DataFrame(videos)
df_channels = pd.DataFrame(channels)

# ─────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────

st.title("🎌 YouTube Japan Lifestyle — Trend Tracker")
st.markdown("Analyse des tendances des chaînes YouTube Lifestyle/Vlog sur le Japon")
st.markdown("---")

# ─────────────────────────────────────────
# KPIs
# ─────────────────────────────────────────

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("📺 Chaînes analysées", len(channels))
with col2:
    st.metric("🎬 Vidéos collectées", len(videos))
with col3:
    total_views = df_videos["view_count"].sum() if not df_videos.empty else 0
    st.metric("👁️ Vues totales", f"{total_views:,}")
with col4:
    avg_views = int(df_videos["view_count"].mean()) if not df_videos.empty else 0
    st.metric("📊 Vues moyennes", f"{avg_views:,}")

st.markdown("---")

# ─────────────────────────────────────────
# ONGLETS
# ─────────────────────────────────────────

tab1, tab2, tab3 = st.tabs(["🧠 Topics ML (BERTopic)", "📊 Analyse Classique", "🏆 Top Vidéos"])

# ─────────────────────────────────────────
# ONGLET 1 : BERTOPIC
# ─────────────────────────────────────────

with tab1:
    st.subheader("🧠 Topics découverts automatiquement par BERTopic")
    st.caption("Les sujets et leur performance sont détectés par Machine Learning sans règles manuelles")

    if ml_stats is not None:
        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("#### 🔥 Performance par topic ML")
            df_ml = ml_stats[ml_stats["bert_topic_label"] != "other"].copy()
            fig = px.bar(
                df_ml.head(10),
                x="bert_topic_label",
                y="avg_views",
                color="avg_views",
                color_continuous_scale="Reds",
                labels={"bert_topic_label": "Topic", "avg_views": "Vues moyennes"},
                text="video_count",
            )
            fig.update_traces(texttemplate='%{text} vidéos', textposition='outside')
            fig.update_layout(showlegend=False, coloraxis_showscale=False,
                            xaxis_tickangle=-30)
            st.plotly_chart(fig, use_container_width=True)

        with col_right:
            st.markdown("#### 🎯 Confiance des prédictions")
            fig = px.bar(
                df_ml.head(10),
                x="bert_topic_label",
                y="avg_confidence",
                color="avg_confidence",
                color_continuous_scale="Greens",
                labels={"bert_topic_label": "Topic", "avg_confidence": "Confiance moyenne"},
            )
            fig.update_layout(showlegend=False, coloraxis_showscale=False,
                            xaxis_tickangle=-30)
            st.plotly_chart(fig, use_container_width=True)

        # Tableau récap
        st.markdown("#### 📋 Récapitulatif des topics")
        df_display = df_ml[["bert_topic_label", "video_count", "avg_views", "avg_likes", "avg_confidence"]].copy()
        df_display.columns = ["Topic", "Vidéos", "Vues moy.", "Likes moy.", "Confiance"]
        df_display["Vues moy."] = df_display["Vues moy."].apply(lambda x: f"{x:,}")
        df_display["Likes moy."] = df_display["Likes moy."].apply(lambda x: f"{x:,}")
        df_display["Confiance"] = df_display["Confiance"].apply(lambda x: f"{x:.0%}")
        st.dataframe(df_display, use_container_width=True, hide_index=True)

    else:
        st.warning("Lance d'abord `python ml/topic_modeling.py` pour générer les topics ML")

# ─────────────────────────────────────────
# ONGLET 2 : ANALYSE CLASSIQUE
# ─────────────────────────────────────────

with tab2:
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("📅 Meilleurs jours pour publier")
        if results and results["best_days"]:
            df_days = pd.DataFrame(results["best_days"])
            day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            df_days["day"] = pd.Categorical(df_days["day"], categories=day_order, ordered=True)
            df_days = df_days.sort_values("day")
            fig = px.bar(
                df_days, x="day", y="avg_views",
                color="avg_views", color_continuous_scale="Blues",
                labels={"day": "Jour", "avg_views": "Vues moyennes"},
            )
            fig.update_layout(showlegend=False, coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("⏱️ Durée idéale des vidéos")
        if results and results["durations"]:
            df_dur = pd.DataFrame(results["durations"])
            fig = px.pie(
                df_dur, names="bucket", values="avg_views",
                hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu,
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("🏷️ Mots-clés tendance dans les titres")
    if results and results["keywords"]:
        df_kw = pd.DataFrame(results["keywords"])
        fig = px.bar(
            df_kw.head(15), x="count", y="word", orientation="h",
            color="count", color_continuous_scale="Greens",
            labels={"word": "Mot-clé", "count": "Occurrences"},
        )
        fig.update_layout(
            yaxis={"categoryorder": "total ascending"},
            showlegend=False, coloraxis_showscale=False
        )
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("📺 Classement des chaînes par abonnés")
    if not df_channels.empty:
        fig = px.bar(
            df_channels.sort_values("subscriber_count", ascending=True),
            x="subscriber_count", y="name", orientation="h",
            color="subscriber_count", color_continuous_scale="Purples",
            labels={"name": "Chaîne", "subscriber_count": "Abonnés"},
        )
        fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────────────────────
# ONGLET 3 : TOP VIDÉOS
# ─────────────────────────────────────────

with tab3:
    st.subheader("🏆 Top 10 vidéos par vues")
    if not df_videos.empty:
        df_top = df_videos.nlargest(10, "view_count")[
            ["title", "channel_name", "view_count", "like_count", "comment_count", "published_at"]
        ].copy()
        df_top.columns = ["Titre", "Chaîne", "Vues", "Likes", "Commentaires", "Publié le"]
        df_top["Vues"]         = df_top["Vues"].apply(lambda x: f"{x:,}")
        df_top["Likes"]        = df_top["Likes"].apply(lambda x: f"{x:,}")
        df_top["Commentaires"] = df_top["Commentaires"].apply(lambda x: f"{x:,}")
        st.dataframe(df_top, use_container_width=True, hide_index=True)

    if df_enriched is not None:
        st.subheader("🧠 Vidéos avec leur topic ML")
        df_ml_videos = df_enriched[["title", "channel_name", "view_count",
                                     "bert_topic_label", "bert_confidence"]].copy()
        df_ml_videos = df_ml_videos.sort_values("view_count", ascending=False).head(20)
        df_ml_videos.columns = ["Titre", "Chaîne", "Vues", "Topic ML", "Confiance"]
        df_ml_videos["Vues"]      = df_ml_videos["Vues"].apply(lambda x: f"{x:,}")
        df_ml_videos["Confiance"] = df_ml_videos["Confiance"].apply(lambda x: f"{x:.0%}")
        st.dataframe(df_ml_videos, use_container_width=True, hide_index=True)