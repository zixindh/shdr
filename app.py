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
    DEFAULT_QUERY_CN,
    DEFAULT_QUERY_GLOBAL,
    collect_feedback,
    compute_daily_hot_topics,
    compute_media_brief,
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


def init_gemini(api_key_override: str = "") -> genai.Client | None:
    key = (api_key_override or "").strip()
    if not key:
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
    source_profile: str,
    auth_config: dict[str, str],
    nonce: int,
) -> list[dict]:
    records = collect_feedback(
        query=query,
        max_items_per_source=max_items,
        include_news=include_news,
        include_social=include_social,
        source_profile=source_profile,
        auth_config=auth_config,
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


def sentiment_chip(label: str, is_cn: bool) -> str:
    if is_cn:
        if label == "positive":
            return "🟢 正向"
        if label == "negative":
            return "🔴 负向"
        return "🟡 中性"
    if label == "positive":
        return "🟢 positive"
    if label == "negative":
        return "🔴 negative"
    return "🟡 neutral"


def sentiment_text(label: str, is_cn: bool) -> str:
    mapping_cn = {"positive": "正向", "neutral": "中性", "negative": "负向"}
    mapping_en = {"positive": "positive", "neutral": "neutral", "negative": "negative"}
    return mapping_cn.get(label, label) if is_cn else mapping_en.get(label, label)


def pretty_score(value: float) -> str:
    return f"{value:+.2f}"


def translate_to_language(text: str, target_lang: str) -> str:
    content = (text or "").strip()
    if not content:
        return ""
    detected = detect_language(content)
    if detected == target_lang or detected == "unknown":
        return content
    translated = translate_text(content, target_lang=target_lang)
    return translated if translated else content


def topic_mask(frame: pd.DataFrame, topic: str) -> pd.Series:
    if not topic or frame.empty:
        return pd.Series([True] * len(frame), index=frame.index)
    pattern = re.escape(topic)
    return frame["title"].fillna("").str.contains(pattern, case=False, regex=True) | frame[
        "text"
    ].fillna("").str.contains(pattern, case=False, regex=True)


if "refresh_nonce" not in st.session_state:
    st.session_state.refresh_nonce = 0

ui_language = st.sidebar.selectbox("Language", ["中文", "English"], index=0)
source_profile = "cn" if ui_language == "中文" else "global"
is_cn_ui = source_profile == "cn"
display_lang = "zh" if is_cn_ui else "en"


def t(cn: str, en: str) -> str:
    return cn if is_cn_ui else en


st.sidebar.title(t("控制台", "Control Center"))
st.markdown(f"## {t('上海迪士尼游客反馈引擎', 'Shanghai Disney Guest Pulse Engine')}")
st.caption(
    t(
        "按天追踪游客反馈，自动提炼每日热点，并统一显示为中文。",
        "Track daily guest sentiment, surface one hot topic per day, and display all content in English.",
    )
)

default_query_by_profile = {
    "cn": DEFAULT_QUERY_CN,
    "global": DEFAULT_QUERY_GLOBAL,
}
default_query = default_query_by_profile[source_profile]
if "query_text" not in st.session_state:
    st.session_state.query_text = default_query
if "query_profile" not in st.session_state:
    st.session_state.query_profile = source_profile
if st.session_state.query_profile != source_profile:
    previous_default = default_query_by_profile.get(st.session_state.query_profile, DEFAULT_QUERY_CN)
    if st.session_state.query_text.strip() == previous_default:
        st.session_state.query_text = default_query
    st.session_state.query_profile = source_profile

query = st.sidebar.text_input(t("监测关键词", "Tracking query"), key="query_text")
refresh_mode = st.sidebar.selectbox(
    t("更新模式", "Update mode"),
    ["Near real-time (5 min)", "Daily snapshot (24h)", "Manual"],
)
max_items = st.sidebar.slider(t("每源抓取上限", "Max items per source"), 20, 160, 80, step=10)
history_days = st.sidebar.slider(t("历史天数", "History window (days)"), 7, 90, 30, step=1)
feed_limit = st.sidebar.slider(t("信息流条数", "Feed items shown"), 20, 200, 80, step=10)
include_news = st.sidebar.toggle(t("包含新闻", "Include news"), value=True)
include_social = st.sidebar.toggle(t("包含社媒", "Include social"), value=True)
focus_hot_topic = st.sidebar.toggle(t("仅看当日热点", "Only hottest topic"), value=False)

with st.sidebar.expander(t("API密钥（可选）", "API keys (optional)"), expanded=False):
    st.caption(
        t(
            "仅在当前会话使用，刷新后可重新输入。",
            "Keys are used only in this session; re-enter after restart.",
        )
    )
    gemini_api_key_input = st.text_input(
        t("Gemini API Key（用于AI摘要）", "Gemini API Key (for AI summary)"),
        type="password",
        value="",
    ).strip()
    apify_token_input = st.text_input(
        t("Apify Token（用于深度社媒抓取）", "Apify Token (for deeper social scraping)"),
        type="password",
        value="",
    ).strip()
    apify_xhs_actor_input = st.text_input("APIFY_XHS_ACTOR_ID", value="").strip()
    apify_douyin_actor_input = st.text_input("APIFY_DOUYIN_ACTOR_ID", value="").strip()
    apify_weibo_actor_input = st.text_input("APIFY_WEIBO_ACTOR_ID", value="").strip()

auth_config: dict[str, str] = {}
if apify_token_input:
    auth_config["APIFY_TOKEN"] = apify_token_input
if apify_xhs_actor_input:
    auth_config["APIFY_XHS_ACTOR_ID"] = apify_xhs_actor_input
if apify_douyin_actor_input:
    auth_config["APIFY_DOUYIN_ACTOR_ID"] = apify_douyin_actor_input
if apify_weibo_actor_input:
    auth_config["APIFY_WEIBO_ACTOR_ID"] = apify_weibo_actor_input

force_refresh = st.sidebar.button(t("立即刷新", "Refresh now"), type="primary")

previous_profile = st.session_state.get("active_source_profile")
profile_changed = previous_profile is not None and previous_profile != source_profile
st.session_state.active_source_profile = source_profile
if force_refresh or profile_changed:
    st.session_state.refresh_nonce += 1

if refresh_mode == "Near real-time (5 min)":
    st_autorefresh(interval=5 * 60 * 1000, key="pulse-realtime")
elif refresh_mode == "Daily snapshot (24h)":
    st_autorefresh(interval=24 * 60 * 60 * 1000, key="pulse-daily")

today_key = datetime.now(CN_TZ).date().isoformat()
all_history = load_history(days_back=history_days)
has_profile_data = any((item.get("source_profile") or "cn") == source_profile for item in all_history)
has_today_snapshot = any(
    item.get("published_day") == today_key and (item.get("source_profile") or "cn") == source_profile
    for item in all_history
)
should_refresh_live = (
    force_refresh
    or profile_changed
    or refresh_mode == "Near real-time (5 min)"
    or (refresh_mode == "Daily snapshot (24h)" and not has_today_snapshot)
    or not has_profile_data
)

if should_refresh_live:
    with st.spinner(t("正在拉取最新信号...", "Pulling latest social + news signals...")):
        refresh_and_store(
            query=query,
            max_items=max_items,
            include_news=include_news,
            include_social=include_social,
            source_profile=source_profile,
            auth_config=auth_config,
            nonce=st.session_state.refresh_nonce,
        )
    all_history = load_history(days_back=history_days)

if not all_history:
    st.warning(t("暂无数据，请点击“立即刷新”或配置连接器。", "No data yet. Click Refresh now or configure connectors."))
    status_df = pd.DataFrame(connector_status(source_profile=source_profile, auth_config=auth_config))
    st.dataframe(status_df, use_container_width=True, hide_index=True)
    st.stop()

df = pd.DataFrame(all_history).drop_duplicates(subset=["id"])
if "source_profile" not in df.columns:
    df["source_profile"] = "cn"
df["source_profile"] = df["source_profile"].fillna("cn")
df = df[df["source_profile"] == source_profile]

if df.empty:
    st.warning(
        t(
            "当前语言模式暂无数据，系统将优先抓取对应来源。请点击“立即刷新”。",
            "No data for this language mode yet. Click Refresh now to pull matching sources.",
        )
    )
    st.dataframe(
        pd.DataFrame(connector_status(source_profile=source_profile, auth_config=auth_config)),
        use_container_width=True,
        hide_index=True,
    )
    st.stop()

df["published_dt"] = pd.to_datetime(df["published_at"], utc=True, errors="coerce").dt.tz_convert(CN_TZ)
df = df.dropna(subset=["published_dt"]).sort_values("published_dt", ascending=False)

platforms = sorted(df["platform"].dropna().unique().tolist())
selected_platforms = st.sidebar.multiselect(t("平台", "Platforms"), options=platforms, default=platforms)
sentiments = ["positive", "neutral", "negative"]
selected_sentiments = st.sidebar.multiselect(t("情绪", "Sentiment"), options=sentiments, default=sentiments)
source_types = sorted(df["source_kind"].dropna().unique().tolist())
selected_source_types = st.sidebar.multiselect(
    t("来源类型", "Source type"), options=source_types, default=source_types
)

days = sorted(df["published_day"].dropna().unique().tolist(), reverse=True)
default_day = today_key if today_key in days else days[0]
selected_day = st.sidebar.selectbox(t("按天查看", "Browse day"), options=days, index=days.index(default_day))

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
selected_hot_topic_display = translate_to_language(selected_hot_topic, target_lang=display_lang)

day_df = filtered_df[filtered_df["published_day"] == selected_day]
display_day_df = day_df.copy()

if focus_hot_topic and selected_hot_topic:
    narrowed = day_df[topic_mask(day_df, selected_hot_topic)]
    if not narrowed.empty:
        display_day_df = narrowed

if display_day_df.empty:
    st.info(t("当前筛选在该日期无记录。", "No records match current filters for this day."))
    st.stop()

avg_score = float(display_day_df["sentiment_score"].mean())
positive_share = float((display_day_df["sentiment_label"] == "positive").mean()) * 100
social_mentions = int((display_day_df["source_kind"] == "social").sum())
news_mentions = int((display_day_df["source_kind"] == "news").sum())
profile_day_df = df[df["published_day"] == selected_day]
profile_news_mentions = int((profile_day_df["source_kind"] == "news").sum())

if include_news and profile_news_mentions == 0:
    st.warning(
        t(
            "该日期暂未抓到新闻，系统已启用新闻兜底检索。可尝试扩大关键词后点击“立即刷新”。",
            "No news found for this day. Fallback news collection is enabled; broaden query and refresh.",
        )
    )

media_brief = compute_media_brief(display_day_df.to_dict("records"), source_profile=source_profile)

st.markdown(
    f"""
    <div class="glass">
        <span class="topic-chip">{escape(t("每日热点", "Hot topic"))}: {escape(selected_hot_topic_display or "overall_sentiment")}</span>
        {f'<span class="tag">{escape(t("本地媒体覆盖", "Local media coverage"))}: {media_brief.get("local_outlet_coverage", 0)*100:.0f}%</span>' if source_profile == "cn" else ''}
    </div>
    """,
    unsafe_allow_html=True,
)

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(
        f'<div class="glass"><div class="kpi">{len(display_day_df)}</div><div class="kpi-label">{t("条目数量", "Mentions")} ({selected_day})</div></div>',
        unsafe_allow_html=True,
    )
with k2:
    st.markdown(
        f'<div class="glass"><div class="kpi">{pretty_score(avg_score)}</div><div class="kpi-label">{t("平均情绪", "Average sentiment")}</div></div>',
        unsafe_allow_html=True,
    )
with k3:
    st.markdown(
        f'<div class="glass"><div class="kpi">{positive_share:.0f}%</div><div class="kpi-label">{t("正向占比", "Positive share")}</div></div>',
        unsafe_allow_html=True,
    )
with k4:
    st.markdown(
        f'<div class="glass"><div class="kpi">{social_mentions}/{news_mentions}</div><div class="kpi-label">{t("社媒与新闻占比", "Social vs news split")}</div></div>',
        unsafe_allow_html=True,
    )

tab_media, tab_hot, tab_pulse, tab_daily, tab_feed, tab_pipeline = st.tabs(
    [
        t("媒体情报", "Media Intelligence"),
        t("每日热点", "Hot Topics"),
        t("总览", "Pulse Board"),
        t("日维度", "Daily Navigator"),
        t("实时流", "Live Feed"),
        t("数据管道", "Pipeline"),
    ]
)

with tab_media:
    st.markdown(f"#### {t('媒体情报驾驶舱', 'Media intelligence cockpit')}")
    c1, c2, c3 = st.columns(3)
    coverage_label = (
        t("本地媒体覆盖率", "Local outlet coverage")
        if source_profile == "cn"
        else t("核心媒体覆盖率", "Core outlet coverage")
    )
    with c1:
        st.markdown(
            f'<div class="glass"><div class="kpi">{media_brief.get("news_mentions", 0)}</div><div class="kpi-label">{t("新闻提及", "News mentions")}</div></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="glass"><div class="kpi">{media_brief.get("negative_mentions", 0)}</div><div class="kpi-label">{t("负向总量", "Negative mentions")}</div></div>',
            unsafe_allow_html=True,
        )
    with c3:
        coverage_pct = int(float(media_brief.get("local_outlet_coverage", 0)) * 100)
        st.markdown(
            f'<div class="glass"><div class="kpi">{coverage_pct}%</div><div class="kpi-label">{coverage_label}</div></div>',
            unsafe_allow_html=True,
        )

    top_outlets = pd.DataFrame(media_brief.get("top_outlets", []))
    risk_table = pd.DataFrame(media_brief.get("risk_table", []))
    if not top_outlets.empty:
        st.markdown(f"##### {t('主流媒体声量', 'Top outlet volume')}")
        st.dataframe(top_outlets.head(12), use_container_width=True, hide_index=True)
    if not risk_table.empty:
        st.markdown(f"##### {t('风险雷达', 'Risk radar')}")
        st.dataframe(risk_table.head(8), use_container_width=True, hide_index=True)
    st.markdown(f"##### {t('建议动作', 'Recommended actions')}")
    for action in media_brief.get("actions", []):
        st.markdown(f"- {action}")

with tab_hot:
    st.markdown(f"#### {t('每日热点摘要', 'Daily hot-topic digest')}")
    if hot_topic_df.empty:
        st.info(t("暂无热点数据。", "No topic data available."))
    else:
        preview = hot_topic_df.sort_values("published_day", ascending=False).head(21).copy()
        preview["coverage"] = (preview["hot_topic_coverage"] * 100).round(0).astype(int).astype(str) + "%"
        preview["hot_topic"] = preview["hot_topic"].apply(lambda x: translate_to_language(x, target_lang=display_lang))
        columns = ["published_day", "hot_topic", "mentions", "hot_topic_hits", "coverage"]
        st.dataframe(
            preview[columns].rename(
                columns={
                    "published_day": t("日期", "day"),
                    "hot_topic": t("热点主题", "hot topic"),
                    "mentions": t("当日总量", "daily mentions"),
                    "hot_topic_hits": t("热点命中", "topic hits"),
                    "coverage": t("覆盖率", "coverage"),
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(t("覆盖率 = 热点命中数 / 当日总条数。", "Coverage = topic hits / daily mentions."))

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
            title=t("每日情绪趋势", "Daily sentiment trend"),
            template="plotly_dark",
        )
        fig_trend.update_layout(height=340, margin=dict(t=40, b=20, l=10, r=10))
        st.plotly_chart(fig_trend, use_container_width=True)
    with c2:
        fig_platform = px.bar(
            platform_df,
            x="platform",
            y="mentions",
            title=f"{t('平台热度', 'Platform volume')} ({selected_day})",
            template="plotly_dark",
        )
        fig_platform.update_layout(height=340, margin=dict(t=40, b=20, l=10, r=10))
        st.plotly_chart(fig_platform, use_container_width=True)

    top_mentions = display_day_df.sort_values("sentiment_score").head(5)
    top_mentions = top_mentions.assign(
        sentiment=top_mentions["sentiment_label"].apply(lambda x: sentiment_text(x, is_cn_ui))
    )
    st.markdown(f"#### {t('负向高优先级信号', 'Most negative signals (priority)')}")
    st.dataframe(
        top_mentions[["published_dt", "platform", "sentiment", "title", "url"]],
        use_container_width=True,
        hide_index=True,
    )

with tab_daily:
    st.markdown(f"#### {t('当日视图', 'Day view')}: {selected_day}")
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
        title=t("每小时热度与情绪", "Hourly volume + sentiment"),
        template="plotly_dark",
    )
    fig_hourly.update_layout(height=320, margin=dict(t=40, b=20, l=10, r=10))
    st.plotly_chart(fig_hourly, use_container_width=True)

    client = init_gemini(gemini_api_key_input)
    if client is not None:
        if st.button(t("生成AI日报", "Generate AI day summary"), key="ai-summary"):
            with st.spinner(t("正在生成...", "Generating summary...")):
                sample_rows = display_day_df.head(40)[
                    ["platform", "sentiment_label", "title", "text"]
                ].to_dict("records")
                prompt_language = "Chinese" if is_cn_ui else "English"
                prompt = (
                    "You are a market intelligence analyst for Shanghai Disney. "
                    f"Write in {prompt_language} only. "
                    "Output: 1) top positives 2) top risks 3) immediate actions in bullet points.\n\n"
                    f"Data for {selected_day}: {sample_rows}"
                )
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                )
                st.markdown(response.text)
    else:
        st.caption(
            t(
                "可在侧边栏输入 Gemini API Key 或配置 GEMINI_API_KEY。",
                "Enter Gemini API key in sidebar or configure GEMINI_API_KEY.",
            )
        )

    preview_df = display_day_df[
        ["published_dt", "platform", "source_kind", "sentiment_label", "sentiment_score", "title", "url"]
    ].rename(columns={"published_dt": "time", "title": "title"})
    preview_df["sentiment"] = preview_df["sentiment_label"].apply(lambda x: sentiment_text(x, is_cn_ui))
    preview_df["title"] = preview_df["title"].apply(lambda x: translate_to_language(x, target_lang=display_lang))
    st.dataframe(
        preview_df.drop(columns=["sentiment_label"]).head(60),
        use_container_width=True,
        hide_index=True,
    )

with tab_feed:
    st.markdown(f"#### {t('实时流', 'Live feed')} · {selected_day}")
    for item in display_day_df.head(feed_limit).to_dict("records"):
        title = translate_to_language(item.get("title", "Untitled"), target_lang=display_lang)
        text = translate_to_language(item.get("text", ""), target_lang=display_lang)
        link = item.get("url", "")
        st.markdown(
            f"""
            <div class="glass">
                <div>
                    <span class="tag">{escape(item.get("platform", "unknown"))}</span>
                    <span class="tag">{escape(item.get("source_kind", "unknown"))}</span>
                    <span class="tag">{escape(sentiment_chip(item.get("sentiment_label", "neutral"), is_cn_ui))}</span>
                    <span class="tag">{escape(item.get("published_day", ""))} {int(item.get("published_hour", 0)):02d}:00</span>
                </div>
                <div style="font-weight:600; margin-top:0.35rem;">{escape(title)}</div>
                <div style="color:#94a3b8; margin-top:0.18rem;">{escape(text[:320])}</div>
                <div style="margin-top:0.35rem;"><a href="{escape(link)}" target="_blank">{escape(t("查看来源", "Open source ↗"))}</a></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

with tab_pipeline:
    st.markdown(f"#### {t('数据管道', 'Ingestion pipeline')}")
    if source_profile == "cn":
        st.markdown(
            """
            - **中文模式默认**：优先抓取小红书/抖音/微博/B站信号，并聚合中文新闻源。
            - **上海本地媒体池**：上观、解放日报、文汇、新民、东方网、看看新闻、Shanghai Daily、市政府等。
            - **自主抓取优先**：内置 DuckDuckGo HTML + Google/Bing RSS + GDELT。
            - **新闻兜底**：主查询 + 多新闻站点 `site:` 检索 + 无地区参数回退。
            - **每日组织**：写入 `data/snapshots/YYYY-MM-DD.json`。
            - **可选密钥增强**：可输入 Apify Token + Actor ID 获取更深层社媒抓取。
            """
        )
    else:
        st.markdown(
            """
            - **English mode = global sources**: YouTube, X/Twitter, Reddit, Instagram.
            - **Global news outlets**: ABC, CNBC, Reuters, BBC, AP.
            - **Own scraping first**: DuckDuckGo HTML + Google/Bing RSS + GDELT + Reddit JSON + YouTube RSS.
            - **Fallback news path**: primary query + outlet `site:` query + locale-agnostic retry.
            - **Daily organization**: persisted in `data/snapshots/YYYY-MM-DD.json`.
            """
        )
    st.dataframe(
        pd.DataFrame(connector_status(source_profile=source_profile, auth_config=auth_config)),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(t("开源连接器调研见 OPEN_SOURCE_CONNECTOR_RESEARCH.md。", "Open-source connector research: OPEN_SOURCE_CONNECTOR_RESEARCH.md"))
    st.caption(
        t(
            "生产建议：使用定时任务并遵守平台条款和频率限制。",
            "Production: run collectors with a scheduler and keep platform ToS/rate-limit compliance checks enabled.",
        )
    )
