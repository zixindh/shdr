from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st
from google import genai
from streamlit_autorefresh import st_autorefresh

from feedback_engine import (
    CN_TZ,
    DEFAULT_QUERY,
    collect_feedback,
    connector_status,
    load_history,
    save_records_by_day,
)

st.set_page_config(
    page_title="Shanghai Disney Guest Pulse",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    .stApp {
        background: radial-gradient(circle at 15% 10%, #172554 0%, #0b1020 35%, #020617 100%);
        color: #e2e8f0;
    }
    .block-container { padding-top: 1.2rem; padding-bottom: 1.2rem; }
    .glass {
        background: rgba(15, 23, 42, 0.6);
        border: 1px solid rgba(148, 163, 184, 0.22);
        border-radius: 14px;
        padding: 0.9rem 1rem;
        margin-bottom: 0.8rem;
        box-shadow: 0 10px 28px rgba(2, 6, 23, 0.35);
    }
    .kpi { font-size: 1.8rem; font-weight: 700; line-height: 1.1; }
    .kpi-label { font-size: 0.85rem; color: #94a3b8; margin-top: 0.25rem; }
    .tag {
        display: inline-block;
        font-size: 0.72rem;
        font-weight: 600;
        padding: 0.15rem 0.45rem;
        border-radius: 999px;
        margin-right: 0.35rem;
        margin-bottom: 0.35rem;
        border: 1px solid rgba(148, 163, 184, 0.35);
        background: rgba(15, 23, 42, 0.7);
    }
    a { color: #93c5fd !important; text-decoration: none !important; }
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_resource
def init_gemini() -> genai.Client | None:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        try:
            key = st.secrets.get("GEMINI_API_KEY", "")
        except Exception:
            key = ""
    return genai.Client(api_key=key) if key else None


@st.cache_data(ttl=300, show_spinner=False)
def refresh_and_store(
    query: str,
    max_items: int,
    include_news: bool,
    include_social: bool,
    nonce: int,
) -> list[dict]:
    records = collect_feedback(
        query=query,
        max_items_per_source=max_items,
        include_news=include_news,
        include_social=include_social,
    )
    save_records_by_day(records)
    return records


def sentiment_chip(label: str) -> str:
    if label == "positive":
        return "🟢 positive"
    if label == "negative":
        return "🔴 negative"
    return "🟡 neutral"


def pretty_score(value: float) -> str:
    return f"{value:+.2f}"


st.markdown("## Shanghai Disney Guest Pulse Engine")
st.caption(
    "Monitor guest sentiment across social + news channels, organized by day with near-real-time refresh."
)

if "refresh_nonce" not in st.session_state:
    st.session_state.refresh_nonce = 0

st.sidebar.title("Control Center")
query = st.sidebar.text_input("Tracking query", value=DEFAULT_QUERY)
refresh_mode = st.sidebar.selectbox(
    "Update mode",
    ["Near real-time (5 min)", "Daily snapshot (24h)", "Manual"],
)
max_items = st.sidebar.slider("Max items per source", 20, 120, 40, step=10)
history_days = st.sidebar.slider("History window (days)", 7, 90, 30, step=1)
include_news = st.sidebar.toggle("Include news", value=True)
include_social = st.sidebar.toggle("Include social", value=True)
force_refresh = st.sidebar.button("Refresh now", type="primary")

if force_refresh:
    st.session_state.refresh_nonce += 1

if refresh_mode == "Near real-time (5 min)":
    st_autorefresh(interval=5 * 60 * 1000, key="pulse-realtime")
elif refresh_mode == "Daily snapshot (24h)":
    st_autorefresh(interval=24 * 60 * 60 * 1000, key="pulse-daily")

today_key = datetime.now(CN_TZ).date().isoformat()
all_history = load_history(days_back=history_days)
has_today_snapshot = any(item.get("published_day") == today_key for item in all_history)
should_refresh_live = (
    force_refresh
    or refresh_mode == "Near real-time (5 min)"
    or (refresh_mode == "Daily snapshot (24h)" and not has_today_snapshot)
)

if should_refresh_live:
    with st.spinner("Pulling latest social + news signals..."):
        refresh_and_store(
            query=query,
            max_items=max_items,
            include_news=include_news,
            include_social=include_social,
            nonce=st.session_state.refresh_nonce,
        )
    all_history = load_history(days_back=history_days)

if not all_history:
    st.warning(
        "No data yet. Click **Refresh now** or configure source connectors to start collecting records."
    )
    status_df = pd.DataFrame(connector_status())
    st.dataframe(status_df, use_container_width=True, hide_index=True)
    st.stop()

df = pd.DataFrame(all_history).drop_duplicates(subset=["id"])
df["published_dt"] = pd.to_datetime(df["published_at"], utc=True, errors="coerce").dt.tz_convert(CN_TZ)
df = df.dropna(subset=["published_dt"]).sort_values("published_dt", ascending=False)

platforms = sorted(df["platform"].dropna().unique().tolist())
selected_platforms = st.sidebar.multiselect("Platforms", options=platforms, default=platforms)
sentiments = ["positive", "neutral", "negative"]
selected_sentiments = st.sidebar.multiselect("Sentiment", options=sentiments, default=sentiments)
source_types = sorted(df["source_kind"].dropna().unique().tolist())
selected_source_types = st.sidebar.multiselect(
    "Source type", options=source_types, default=source_types
)

days = sorted(df["published_day"].dropna().unique().tolist(), reverse=True)
default_day = today_key if today_key in days else days[0]
selected_day = st.sidebar.selectbox("Browse day", options=days, index=days.index(default_day))

filtered_df = df[
    df["platform"].isin(selected_platforms)
    & df["sentiment_label"].isin(selected_sentiments)
    & df["source_kind"].isin(selected_source_types)
]
day_df = filtered_df[filtered_df["published_day"] == selected_day]

if day_df.empty:
    st.info("No records match current filters for this day.")
    st.stop()

avg_score = float(day_df["sentiment_score"].mean()) if len(day_df) else 0.0
positive_share = float((day_df["sentiment_label"] == "positive").mean()) * 100
social_mentions = int((day_df["source_kind"] == "social").sum())
news_mentions = int((day_df["source_kind"] == "news").sum())

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(
        f'<div class="glass"><div class="kpi">{len(day_df)}</div><div class="kpi-label">Mentions on {selected_day}</div></div>',
        unsafe_allow_html=True,
    )
with k2:
    st.markdown(
        f'<div class="glass"><div class="kpi">{pretty_score(avg_score)}</div><div class="kpi-label">Average sentiment</div></div>',
        unsafe_allow_html=True,
    )
with k3:
    st.markdown(
        f'<div class="glass"><div class="kpi">{positive_share:.0f}%</div><div class="kpi-label">Positive share</div></div>',
        unsafe_allow_html=True,
    )
with k4:
    st.markdown(
        f'<div class="glass"><div class="kpi">{social_mentions}/{news_mentions}</div><div class="kpi-label">Social / news split</div></div>',
        unsafe_allow_html=True,
    )

tab_pulse, tab_daily, tab_feed, tab_pipeline = st.tabs(
    ["Pulse Board", "Daily Navigator", "Live Feed", "Pipeline"]
)

with tab_pulse:
    trend_df = (
        filtered_df.groupby("published_day", as_index=False)
        .agg(avg_sentiment=("sentiment_score", "mean"), mentions=("id", "count"))
        .sort_values("published_day")
    )
    platform_df = (
        day_df.groupby("platform", as_index=False).agg(mentions=("id", "count")).sort_values(
            "mentions", ascending=False
        )
    )
    c1, c2 = st.columns(2)
    with c1:
        fig_trend = px.line(
            trend_df,
            x="published_day",
            y="avg_sentiment",
            markers=True,
            title="Daily Sentiment Trend",
            template="plotly_dark",
        )
        fig_trend.update_layout(height=340, margin=dict(t=40, b=20, l=10, r=10))
        st.plotly_chart(fig_trend, use_container_width=True)
    with c2:
        fig_platform = px.bar(
            platform_df,
            x="platform",
            y="mentions",
            title=f"Platform Volume on {selected_day}",
            template="plotly_dark",
        )
        fig_platform.update_layout(height=340, margin=dict(t=40, b=20, l=10, r=10))
        st.plotly_chart(fig_platform, use_container_width=True)

    top_mentions = day_df.sort_values("sentiment_score").head(5)
    st.markdown("#### Most negative signals (priority to investigate)")
    st.dataframe(
        top_mentions[["published_dt", "platform", "sentiment_label", "title", "url"]],
        use_container_width=True,
        hide_index=True,
    )

with tab_daily:
    st.markdown(f"#### Day view: {selected_day}")
    hourly = (
        day_df.groupby("published_hour", as_index=False)
        .agg(mentions=("id", "count"), avg_sentiment=("sentiment_score", "mean"))
        .sort_values("published_hour")
    )
    fig_hourly = px.bar(
        hourly,
        x="published_hour",
        y="mentions",
        color="avg_sentiment",
        color_continuous_scale="RdYlGn",
        range_color=(-1, 1),
        title="Hourly mention volume + sentiment",
        template="plotly_dark",
    )
    fig_hourly.update_layout(height=320, margin=dict(t=40, b=20, l=10, r=10))
    st.plotly_chart(fig_hourly, use_container_width=True)

    client = init_gemini()
    if client is not None:
        if st.button("Generate AI day summary", key="ai-summary"):
            with st.spinner("Generating summary..."):
                sample_rows = day_df.head(40)[
                    ["platform", "sentiment_label", "title", "text"]
                ].to_dict("records")
                prompt = (
                    "You are a market intelligence analyst. Summarize guest feedback about Shanghai Disney. "
                    "Output: 1) top positives 2) top risks 3) immediate actions in bullet points.\n\n"
                    f"Data for {selected_day}: {sample_rows}"
                )
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                )
                st.markdown(response.text)
    else:
        st.caption("Set GEMINI_API_KEY to enable AI day summaries.")

    view_df = day_df[
        [
            "published_dt",
            "platform",
            "source_kind",
            "sentiment_label",
            "sentiment_score",
            "title",
            "url",
        ]
    ].rename(columns={"published_dt": "time_cn"})
    st.dataframe(view_df, use_container_width=True, hide_index=True)

with tab_feed:
    st.markdown(f"#### Live feed · {selected_day}")
    for item in day_df.head(120).to_dict("records"):
        title = item.get("title", "Untitled")
        text = item.get("text", "")
        link = item.get("url", "")
        st.markdown(
            f"""
            <div class="glass">
                <div>
                    <span class="tag">{item.get("platform", "unknown")}</span>
                    <span class="tag">{item.get("source_kind", "unknown")}</span>
                    <span class="tag">{sentiment_chip(item.get("sentiment_label", "neutral"))}</span>
                    <span class="tag">{item.get("published_day")} {int(item.get("published_hour", 0)):02d}:00</span>
                </div>
                <div style="font-weight:600; margin-top:0.35rem;">{title}</div>
                <div style="color:#94a3b8; margin-top:0.25rem;">{text[:280]}</div>
                <div style="margin-top:0.35rem;"><a href="{link}" target="_blank">Open source ↗</a></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

with tab_pipeline:
    st.markdown("#### Ingestion blueprint (daily + near-real-time)")
    st.markdown(
        """
        - **Xiaohongshu / Douyin / Weibo direct scraping**: use Apify actors (configure `APIFY_TOKEN` + actor IDs).
        - **Fallback social discovery**: Google News RSS with `site:` filters for each social domain.
        - **News coverage**: Shanghai Disney query from Google News RSS.
        - **Daily organization**: records are persisted to `data/snapshots/YYYY-MM-DD.json`.
        - **Refresh modes**: manual, 24h snapshot, or 5-min auto-refresh.
        """
    )
    st.dataframe(pd.DataFrame(connector_status()), use_container_width=True, hide_index=True)
    st.caption(
        "For production: run collectors via scheduler (cron/GitHub Actions) and keep platform ToS compliance checks enabled."
    )
