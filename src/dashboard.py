# src/dashboard.py

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analyzer import run_analysis
from database import get_all_videos, get_all_channels

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
    st.info("Données collectées via YouTube Data API v3")

# ─────────────────────────────────────────
# CHARGEMENT DES DONNÉES
# ─────────────────────────────────────────

@st.cache_data(ttl=3600)  # cache 1h
def load_data():
    videos   = get_all_videos()
    channels = get_all_channels()
    results  = run_analysis()
    return videos, channels, results

with st.spinner("Chargement des données..."):
    videos, channels, results = load_data()

# Filtre par chaîne si sélectionnée
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
# LIGNE 1 : SUJETS + JOURS
# ─────────────────────────────────────────

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🔥 Sujets les plus performants")
    if results and results["topics"]:
        df_topics = pd.DataFrame(results["topics"])
        fig = px.bar(
            df_topics,
            x="topic",
            y="avg_views",
            color="avg_views",
            color_continuous_scale="Reds",
            labels={"topic": "Sujet", "avg_views": "Vues moyennes"},
            text="video_count",
        )
        fig.update_traces(texttemplate='%{text} vidéos', textposition='outside')
        fig.update_layout(showlegend=False, coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader("📅 Meilleurs jours pour publier")
    if results and results["best_days"]:
        df_days = pd.DataFrame(results["best_days"])
        # Ordre logique des jours
        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        df_days["day"] = pd.Categorical(df_days["day"], categories=day_order, ordered=True)
        df_days = df_days.sort_values("day")

        fig = px.bar(
            df_days,
            x="day",
            y="avg_views",
            color="avg_views",
            color_continuous_scale="Blues",
            labels={"day": "Jour", "avg_views": "Vues moyennes"},
        )
        fig.update_layout(showlegend=False, coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────────────────────
# LIGNE 2 : DURÉE + MOTS-CLÉS
# ─────────────────────────────────────────

col_left2, col_right2 = st.columns(2)

with col_left2:
    st.subheader("⏱️ Durée idéale des vidéos")
    if results and results["durations"]:
        df_dur = pd.DataFrame(results["durations"])
        fig = px.pie(
            df_dur,
            names="bucket",
            values="avg_views",
            hole=0.4,
            color_discrete_sequence=px.colors.sequential.RdBu,
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)

with col_right2:
    st.subheader("🏷️ Mots-clés tendance dans les titres")
    if results and results["keywords"]:
        df_kw = pd.DataFrame(results["keywords"])
        fig = px.bar(
            df_kw.head(15),
            x="count",
            y="word",
            orientation="h",
            color="count",
            color_continuous_scale="Greens",
            labels={"word": "Mot-clé", "count": "Occurrences"},
        )
        fig.update_layout(
            yaxis={"categoryorder": "total ascending"},
            showlegend=False,
            coloraxis_showscale=False
        )
        st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────────────────────
# LIGNE 3 : TOP VIDÉOS
# ─────────────────────────────────────────

st.markdown("---")
st.subheader("🏆 Top vidéos par vues")

if not df_videos.empty:
    df_top = df_videos.nlargest(10, "view_count")[
        ["title", "channel_name", "view_count", "like_count", "comment_count", "published_at"]
    ].copy()
    df_top.columns = ["Titre", "Chaîne", "Vues", "Likes", "Commentaires", "Publié le"]
    df_top["Vues"]        = df_top["Vues"].apply(lambda x: f"{x:,}")
    df_top["Likes"]       = df_top["Likes"].apply(lambda x: f"{x:,}")
    df_top["Commentaires"] = df_top["Commentaires"].apply(lambda x: f"{x:,}")
    st.dataframe(df_top, use_container_width=True, hide_index=True)

# ─────────────────────────────────────────
# LIGNE 4 : CHAÎNES
# ─────────────────────────────────────────

st.markdown("---")
st.subheader("📺 Classement des chaînes par abonnés")

if not df_channels.empty:
    fig = px.bar(
        df_channels.sort_values("subscriber_count", ascending=True),
        x="subscriber_count",
        y="name",
        orientation="h",
        color="subscriber_count",
        color_continuous_scale="Purples",
        labels={"name": "Chaîne", "subscriber_count": "Abonnés"},
    )
    fig.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)