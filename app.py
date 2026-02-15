from __future__ import annotations

import os
import re
from datetime import datetime
from html import escape

import pandas as pd
import plotly.express as px
import streamlit as st
from google import genai
from streamlit_autorefresh import st_autorefresh

from feedback_engine import (
    CN_TZ,
    DEFAULT_QUERY,
    collect_feedback,
    compute_daily_hot_topics,
    connector_status,
    detect_language,
    load_history,
    save_records_by_day,
)

try:
    from deep_translator import GoogleTranslator
except Exception:
    GoogleTranslator = None

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
    .topic-chip {
        display: inline-block;
        font-size: 0.9rem;
        font-weight: 700;
        padding: 0.25rem 0.6rem;
        border-radius: 10px;
        border: 1px solid rgba(125, 211, 252, 0.45);
        background: rgba(14, 116, 144, 0.22);
        margin-right: 0.6rem;
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


@st.cache_data(ttl=86400, show_spinner=False)
def translate_text(text: str, target_lang: str) -> str:
    content = " ".join((text or "").split())
    if not content:
        return ""
    if GoogleTranslator is None:
        return ""
    try:
        target = "zh-CN" if target_lang == "zh" else "en"
        # External translators can choke on long strings; keep snippets concise.
        return (GoogleTranslator(source="auto", target=target).translate(content[:1200]) or "").strip()
    except Exception:
        return ""


def sentiment_chip(label: str) -> str:
    if label == "positive":
        return "🟢 positive / 正向"
    if label == "negative":
        return "🔴 negative / 负向"
    return "🟡 neutral / 中性"


def pretty_score(value: float) -> str:
    return f"{value:+.2f}"


def translate_opposite(text: str) -> str:
    content = (text or "").strip()
    if not content:
        return ""
    source_lang = detect_language(content)
    target_lang = "en" if source_lang == "zh" else "zh"
    translated = translate_text(content, target_lang=target_lang)
    return translated if translated else "Translation unavailable / 暂无翻译"


def topic_mask(frame: pd.DataFrame, topic: str) -> pd.Series:
    if not topic or frame.empty:
        return pd.Series([True] * len(frame), index=frame.index)
    pattern = re.escape(topic)
    return frame["title"].fillna("").str.contains(pattern, case=False, regex=True) | frame[
        "text"
    ].fillna("").str.contains(pattern, case=False, regex=True)


st.markdown("## Shanghai Disney Guest Pulse Engine | 上海迪士尼游客反馈引擎")
st.caption(
    "Track daily guest sentiment from social + news, surface one hottest topic each day, and browse in bilingual mode. "
    "按天追踪游客反馈，自动提炼每日热点，并提供双语阅读。"
)

if "refresh_nonce" not in st.session_state:
    st.session_state.refresh_nonce = 0

st.sidebar.title("Control Center | 控制台")
query = st.sidebar.text_input("Tracking query | 监测关键词", value=DEFAULT_QUERY)
refresh_mode = st.sidebar.selectbox(
    "Update mode | 更新模式",
    ["Near real-time (5 min)", "Daily snapshot (24h)", "Manual"],
)
max_items = st.sidebar.slider("Max items per source | 每源抓取上限", 20, 120, 40, step=10)
history_days = st.sidebar.slider("History window (days) | 历史天数", 7, 90, 30, step=1)
feed_limit = st.sidebar.slider("Feed items shown | 信息流条数", 20, 120, 50, step=10)
include_news = st.sidebar.toggle("Include news | 包含新闻", value=True)
include_social = st.sidebar.toggle("Include social | 包含社媒", value=True)
show_translation = st.sidebar.toggle("Bilingual translation | 双语翻译", value=True)
focus_hot_topic = st.sidebar.toggle("Only hottest topic | 仅看当日热点", value=False)
force_refresh = st.sidebar.button("Refresh now | 立即刷新", type="primary")

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
    with st.spinner("Pulling latest social + news signals... 正在拉取最新信号..."):
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
        "No data yet. Click **Refresh now** or configure connectors. "
        "暂无数据，请点击刷新或配置抓取连接器。"
    )
    status_df = pd.DataFrame(connector_status())
    st.dataframe(status_df, use_container_width=True, hide_index=True)
    st.stop()

df = pd.DataFrame(all_history).drop_duplicates(subset=["id"])
df["published_dt"] = pd.to_datetime(df["published_at"], utc=True, errors="coerce").dt.tz_convert(CN_TZ)
df = df.dropna(subset=["published_dt"]).sort_values("published_dt", ascending=False)

platforms = sorted(df["platform"].dropna().unique().tolist())
selected_platforms = st.sidebar.multiselect("Platforms | 平台", options=platforms, default=platforms)
sentiments = ["positive", "neutral", "negative"]
selected_sentiments = st.sidebar.multiselect("Sentiment | 情绪", options=sentiments, default=sentiments)
source_types = sorted(df["source_kind"].dropna().unique().tolist())
selected_source_types = st.sidebar.multiselect(
    "Source type | 来源类型", options=source_types, default=source_types
)

days = sorted(df["published_day"].dropna().unique().tolist(), reverse=True)
default_day = today_key if today_key in days else days[0]
selected_day = st.sidebar.selectbox("Browse day | 按天查看", options=days, index=days.index(default_day))

filtered_df = df[
    df["platform"].isin(selected_platforms)
    & df["sentiment_label"].isin(selected_sentiments)
    & df["source_kind"].isin(selected_source_types)
]

hot_topic_df = pd.DataFrame(compute_daily_hot_topics(filtered_df.to_dict("records")))
hot_topic_map = (
    {}
    if hot_topic_df.empty
    else hot_topic_df.set_index("published_day")["hot_topic"].to_dict()
)
selected_hot_topic = hot_topic_map.get(selected_day, "")
selected_hot_topic_translation = (
    translate_opposite(selected_hot_topic) if show_translation and selected_hot_topic else ""
)

day_df = filtered_df[filtered_df["published_day"] == selected_day]
display_day_df = day_df.copy()

if focus_hot_topic and selected_hot_topic:
    narrowed = day_df[topic_mask(day_df, selected_hot_topic)]
    if not narrowed.empty:
        display_day_df = narrowed

if display_day_df.empty:
    st.info("No records match current filters for this day. 当前筛选在该日期无记录。")
    st.stop()

avg_score = float(display_day_df["sentiment_score"].mean())
positive_share = float((display_day_df["sentiment_label"] == "positive").mean()) * 100
social_mentions = int((display_day_df["source_kind"] == "social").sum())
news_mentions = int((display_day_df["source_kind"] == "news").sum())

st.markdown(
    f"""
    <div class="glass">
        <span class="topic-chip">Hot topic / 每日热点: {escape(selected_hot_topic or "overall_sentiment")}</span>
        <span style="color:#94a3b8;">{escape(selected_hot_topic_translation) if selected_hot_topic_translation else ""}</span>
    </div>
    """,
    unsafe_allow_html=True,
)

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(
        f'<div class="glass"><div class="kpi">{len(display_day_df)}</div><div class="kpi-label">Mentions / 条目 ({selected_day})</div></div>',
        unsafe_allow_html=True,
    )
with k2:
    st.markdown(
        f'<div class="glass"><div class="kpi">{pretty_score(avg_score)}</div><div class="kpi-label">Avg sentiment / 平均情绪</div></div>',
        unsafe_allow_html=True,
    )
with k3:
    st.markdown(
        f'<div class="glass"><div class="kpi">{positive_share:.0f}%</div><div class="kpi-label">Positive share / 正向占比</div></div>',
        unsafe_allow_html=True,
    )
with k4:
    st.markdown(
        f'<div class="glass"><div class="kpi">{social_mentions}/{news_mentions}</div><div class="kpi-label">Social / News split</div></div>',
        unsafe_allow_html=True,
    )

tab_hot, tab_pulse, tab_daily, tab_feed, tab_pipeline = st.tabs(
    [
        "Hot Topics / 每日热点",
        "Pulse Board / 总览",
        "Daily Navigator / 日维度",
        "Live Feed / 实时流",
        "Pipeline / 数据管道",
    ]
)

with tab_hot:
    st.markdown("#### Daily hot-topic digest | 每日热点摘要")
    if hot_topic_df.empty:
        st.info("No topic data available. 暂无热点数据。")
    else:
        preview = hot_topic_df.sort_values("published_day", ascending=False).head(21).copy()
        preview["coverage"] = (preview["hot_topic_coverage"] * 100).round(0).astype(int).astype(str) + "%"
        if show_translation:
            preview["hot_topic_translation"] = preview["hot_topic"].apply(translate_opposite)
        columns = ["published_day", "hot_topic", "mentions", "hot_topic_hits", "coverage"]
        if show_translation:
            columns.insert(2, "hot_topic_translation")
        st.dataframe(
            preview[columns].rename(
                columns={
                    "published_day": "day",
                    "hot_topic": "hot topic (original)",
                    "hot_topic_translation": "hot topic (translation)",
                    "mentions": "daily mentions",
                    "hot_topic_hits": "topic hits",
                    "coverage": "coverage",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            "Coverage = topic hits / daily mentions. This keeps each day focused on one dominant signal."
            " 覆盖率=热点命中数/当日总条数，用于降低信息过载。"
        )

with tab_pulse:
    trend_df = (
        filtered_df.groupby("published_day", as_index=False)
        .agg(avg_sentiment=("sentiment_score", "mean"), mentions=("id", "count"))
        .sort_values("published_day")
    )
    platform_df = (
        display_day_df.groupby("platform", as_index=False)
        .agg(mentions=("id", "count"))
        .sort_values("mentions", ascending=False)
    )
    c1, c2 = st.columns(2)
    with c1:
        fig_trend = px.line(
            trend_df,
            x="published_day",
            y="avg_sentiment",
            markers=True,
            title="Daily Sentiment Trend | 每日情绪趋势",
            template="plotly_dark",
        )
        fig_trend.update_layout(height=340, margin=dict(t=40, b=20, l=10, r=10))
        st.plotly_chart(fig_trend, use_container_width=True)
    with c2:
        fig_platform = px.bar(
            platform_df,
            x="platform",
            y="mentions",
            title=f"Platform Volume ({selected_day}) | 平台热度",
            template="plotly_dark",
        )
        fig_platform.update_layout(height=340, margin=dict(t=40, b=20, l=10, r=10))
        st.plotly_chart(fig_platform, use_container_width=True)

    top_mentions = display_day_df.sort_values("sentiment_score").head(5)
    st.markdown("#### Most negative signals (priority) | 负向高优先级信号")
    st.dataframe(
        top_mentions[["published_dt", "platform", "sentiment_label", "title", "url"]],
        use_container_width=True,
        hide_index=True,
    )

with tab_daily:
    st.markdown(f"#### Day view: {selected_day} | 当日视图")
    hourly = (
        display_day_df.groupby("published_hour", as_index=False)
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
        title="Hourly volume + sentiment | 每小时热度与情绪",
        template="plotly_dark",
    )
    fig_hourly.update_layout(height=320, margin=dict(t=40, b=20, l=10, r=10))
    st.plotly_chart(fig_hourly, use_container_width=True)

    client = init_gemini()
    if client is not None:
        if st.button("Generate AI day summary | 生成AI日报", key="ai-summary"):
            with st.spinner("Generating summary... 正在生成..."):
                sample_rows = display_day_df.head(40)[
                    ["platform", "sentiment_label", "title", "text"]
                ].to_dict("records")
                prompt = (
                    "You are a market intelligence analyst for Shanghai Disney. "
                    "Write bilingual output (English + Chinese). "
                    "Output: 1) top positives 2) top risks 3) immediate actions in bullet points.\n\n"
                    f"Data for {selected_day}: {sample_rows}"
                )
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                )
                st.markdown(response.text)
    else:
        st.caption("Set GEMINI_API_KEY to enable AI day summaries. 配置后可生成AI双语日报。")

    preview_df = display_day_df[
        ["published_dt", "platform", "source_kind", "sentiment_label", "sentiment_score", "title", "url"]
    ].rename(columns={"published_dt": "time_cn", "title": "title_original"})
    if show_translation:
        preview_df["title_translation"] = preview_df["title_original"].apply(translate_opposite)
    st.dataframe(preview_df.head(60), use_container_width=True, hide_index=True)

with tab_feed:
    st.markdown(f"#### Live feed · {selected_day} | 实时流")
    for item in display_day_df.head(feed_limit).to_dict("records"):
        title = item.get("title", "Untitled")
        text = item.get("text", "")
        link = item.get("url", "")
        translated_title = translate_opposite(title) if show_translation else ""
        translated_text = translate_opposite(text[:500]) if show_translation else ""
        st.markdown(
            f"""
            <div class="glass">
                <div>
                    <span class="tag">{escape(item.get("platform", "unknown"))}</span>
                    <span class="tag">{escape(item.get("source_kind", "unknown"))}</span>
                    <span class="tag">{escape(sentiment_chip(item.get("sentiment_label", "neutral")))}</span>
                    <span class="tag">{escape(item.get("published_day", ""))} {int(item.get("published_hour", 0)):02d}:00</span>
                </div>
                <div style="font-weight:600; margin-top:0.35rem;">Original / 原文: {escape(title)}</div>
                <div style="color:#94a3b8; margin-top:0.18rem;">{escape(text[:320])}</div>
                {f'<div style="font-weight:600; margin-top:0.35rem;">Translation / 翻译: {escape(translated_title)}</div><div style="color:#94a3b8; margin-top:0.18rem;">{escape(translated_text)}</div>' if show_translation else ''}
                <div style="margin-top:0.35rem;"><a href="{escape(link)}" target="_blank">Open source ↗ / 查看来源</a></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

with tab_pipeline:
    st.markdown("#### Ingestion blueprint (daily + near-real-time) | 数据管道")
    st.markdown(
        """
        - **Xiaohongshu / Douyin / Weibo direct scraping**: use Apify actors (`APIFY_TOKEN` + actor IDs).
        - **Fallback social discovery**: Google News RSS with `site:` filters.
        - **News coverage**: Shanghai Disney query via RSS.
        - **Daily organization**: persisted in `data/snapshots/YYYY-MM-DD.json`.
        - **Hot-topic extraction**: one dominant topic per day to reduce overload.
        - **Bilingual layer**: keep original text, append translation.
        """
    )
    st.dataframe(pd.DataFrame(connector_status()), use_container_width=True, hide_index=True)
    st.caption(
        "For production: run collectors with a scheduler and keep platform ToS/rate-limit compliance checks enabled."
        " 生产建议：使用定时任务并遵守平台条款和频率限制。"
    )
