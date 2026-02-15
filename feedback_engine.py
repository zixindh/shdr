from __future__ import annotations

import hashlib
import html
import json
import os
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import feedparser
import requests
from dateutil import parser as date_parser

CN_TZ = timezone(timedelta(hours=8))
SNAPSHOT_DIR = Path(__file__).resolve().parent / "data" / "snapshots"
DEFAULT_QUERY = "上海迪士尼 OR Shanghai Disney"

SOCIAL_DOMAINS = {
    "Xiaohongshu": "xiaohongshu.com",
    "Douyin": "douyin.com",
    "Weibo": "weibo.com",
    "Bilibili": "bilibili.com",
}

APIFY_ACTOR_ENV = {
    "Xiaohongshu": "APIFY_XHS_ACTOR_ID",
    "Douyin": "APIFY_DOUYIN_ACTOR_ID",
    "Weibo": "APIFY_WEIBO_ACTOR_ID",
}

POSITIVE_WORDS = {
    "amazing",
    "awesome",
    "beautiful",
    "excellent",
    "fun",
    "great",
    "happy",
    "love",
    "perfect",
    "recommend",
    "smooth",
    "wow",
    "不错",
    "丝滑",
    "值",
    "值得",
    "开心",
    "惊艳",
    "推荐",
    "满意",
    "精彩",
    "顺畅",
    "震撼",
}

NEGATIVE_WORDS = {
    "bad",
    "broken",
    "crowded",
    "delay",
    "disappointed",
    "expensive",
    "poor",
    "refund",
    "slow",
    "terrible",
    "worst",
    "坑",
    "失望",
    "差",
    "排队",
    "拥挤",
    "故障",
    "昂贵",
    "无语",
    "糟糕",
    "贵",
}

HOT_TOPIC_STOPWORDS_EN = {
    "about",
    "after",
    "against",
    "been",
    "from",
    "have",
    "into",
    "just",
    "more",
    "news",
    "park",
    "resort",
    "shanghai",
    "disney",
    "today",
    "trip",
    "visitor",
    "with",
}

HOT_TOPIC_STOPWORDS_ZH = {
    "上海",
    "上海迪士尼",
    "迪士尼",
    "乐园",
    "度假区",
    "游客",
    "体验",
    "新闻",
    "反馈",
    "感觉",
    "现场",
    "分享",
    "网友",
}

HOT_TOPIC_WEB_NOISE = {
    "com",
    "cn",
    "net",
    "org",
    "www",
    "http",
    "https",
    "html",
    "news",
    "nbsp",
    "amp",
    "quot",
    "lt",
    "gt",
}


def _contains_cjk(token: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in token)


def _count_hits(text: str, keywords: set[str]) -> int:
    if not text:
        return 0

    lowered = text.lower()
    hits = 0
    for word in keywords:
        token = word.lower()
        if _contains_cjk(token):
            hits += lowered.count(token)
            continue
        hits += len(re.findall(rf"\b{re.escape(token)}\b", lowered))
    return hits


def score_sentiment(text: str) -> tuple[float, str]:
    positive = _count_hits(text, POSITIVE_WORDS)
    negative = _count_hits(text, NEGATIVE_WORDS)
    total = positive + negative
    score = 0.0 if total == 0 else (positive - negative) / total

    if score >= 0.2:
        return score, "positive"
    if score <= -0.2:
        return score, "negative"
    return score, "neutral"


def _safe_parse_dt(value: Any) -> datetime:
    if value is None or value == "":
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        timestamp = value / 1000 if value > 10_000_000_000 else value
        parsed = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    else:
        try:
            parsed = date_parser.parse(str(value))
        except Exception:
            parsed = datetime.now(timezone.utc)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _first(item: dict[str, Any], keys: list[str], default: str = "") -> str:
    for key in keys:
        value = item.get(key)
        if value is None:
            continue
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)):
            return str(value)
    return default


def _build_record(
    source_kind: str,
    platform: str,
    title: str,
    text: str,
    url: str,
    author: str,
    published_at: Any,
) -> dict[str, Any]:
    published = _safe_parse_dt(published_at)
    published_cn = published.astimezone(CN_TZ)
    body = f"{title}\n{text}".strip()
    sentiment_score, sentiment_label = score_sentiment(body)
    base_id = f"{platform}|{url}|{title}|{published.isoformat()}"

    return {
        "id": hashlib.sha1(base_id.encode("utf-8")).hexdigest(),
        "source_kind": source_kind,
        "platform": platform,
        "title": title or "Untitled post",
        "text": text,
        "url": url,
        "author": author or "Unknown",
        "published_at": published.isoformat(),
        "published_day": published_cn.date().isoformat(),
        "published_hour": published_cn.hour,
        "sentiment_score": round(sentiment_score, 3),
        "sentiment_label": sentiment_label,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def _google_news_feed(query: str, max_items: int, source_kind: str, platform: str) -> list[dict[str, Any]]:
    encoded = quote_plus(query)
    url = (
        "https://news.google.com/rss/search"
        f"?q={encoded}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    )
    feed = feedparser.parse(url)
    records: list[dict[str, Any]] = []

    for entry in feed.entries[:max_items]:
        summary = re.sub(r"<[^>]+>", " ", entry.get("summary", ""))
        record = _build_record(
            source_kind=source_kind,
            platform=platform,
            title=entry.get("title", "").strip(),
            text=re.sub(r"\s+", " ", summary).strip(),
            url=entry.get("link", "").strip(),
            author=_first(entry, ["author", "source"]),
            published_at=entry.get("published") or entry.get("updated"),
        )
        records.append(record)
    return records


def _run_apify_actor(actor_id: str, token: str, actor_input: dict[str, Any]) -> list[dict[str, Any]]:
    run_url = (
        f"https://api.apify.com/v2/acts/{actor_id}/runs"
        f"?token={token}&waitForFinish=45"
    )
    try:
        run_response = requests.post(run_url, json=actor_input, timeout=60)
        run_response.raise_for_status()
        run_json = run_response.json().get("data", {})
        dataset_id = run_json.get("defaultDatasetId")
        if not dataset_id:
            return []

        data_url = (
            f"https://api.apify.com/v2/datasets/{dataset_id}/items"
            f"?token={token}&clean=true&format=json"
        )
        data_response = requests.get(data_url, timeout=60)
        data_response.raise_for_status()
        items = data_response.json()
        return items if isinstance(items, list) else []
    except Exception:
        return []


def _fetch_apify_platform(platform: str, query: str, max_items: int) -> list[dict[str, Any]]:
    token = os.getenv("APIFY_TOKEN", "").strip()
    actor_env = APIFY_ACTOR_ENV.get(platform)
    actor_id = os.getenv(actor_env, "").strip() if actor_env else ""
    if not token or not actor_id:
        return []

    actor_input = {
        "search": query,
        "searchTerms": [query],
        "keywords": [query],
        "limit": max_items,
        "maxItems": max_items,
        "resultsLimit": max_items,
        "sort": "latest",
    }
    raw_items = _run_apify_actor(actor_id=actor_id, token=token, actor_input=actor_input)
    records: list[dict[str, Any]] = []

    for item in raw_items:
        title = _first(item, ["title", "name", "noteTitle", "desc", "caption"])
        text = _first(item, ["text", "content", "description", "summary", "noteContent", "desc"])
        url = _first(item, ["url", "shareUrl", "postUrl", "link"])
        author = _first(item, ["author", "nickname", "userName", "user", "authorName"])
        published = _first(
            item,
            [
                "publishTime",
                "publishedAt",
                "createTime",
                "createdAt",
                "timestamp",
                "time",
            ],
        )
        if not title and not text:
            continue
        records.append(
            _build_record(
                source_kind="social",
                platform=platform,
                title=title,
                text=text,
                url=url,
                author=author,
                published_at=published,
            )
        )
    return records


def _dedupe(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for record in records:
        seen.setdefault(record["id"], record)
    return sorted(seen.values(), key=lambda item: item["published_at"], reverse=True)


def detect_language(text: str) -> str:
    sample = (text or "").strip()
    if not sample:
        return "unknown"
    if _contains_cjk(sample):
        return "zh"
    if re.search(r"[A-Za-z]", sample):
        return "en"
    return "unknown"


def _normalize_topic_token(token: str) -> str:
    raw = (token or "").strip()
    if not raw:
        return ""

    if _contains_cjk(raw):
        cleaned = re.sub(r"(上海迪士尼|上海|迪士尼|乐园|度假区)", "", raw).strip()
        if len(cleaned) < 2 or cleaned in HOT_TOPIC_STOPWORDS_ZH:
            return ""
        return cleaned

    cleaned = re.sub(r"[^A-Za-z0-9]+", "", raw).lower()
    if (
        len(cleaned) < 3
        or cleaned in HOT_TOPIC_STOPWORDS_EN
        or cleaned in HOT_TOPIC_WEB_NOISE
    ):
        return ""
    if cleaned.isdigit():
        return ""
    return cleaned


def extract_topic_terms(text: str) -> list[str]:
    sample = html.unescape((text or "").strip()).replace("\xa0", " ")
    if not sample:
        return []
    sample = re.sub(r"&[A-Za-z]+;", " ", sample)
    sample = re.sub(r"https?://\S+|www\.\S+", " ", sample)
    sample = re.sub(r"\b[a-z0-9.-]+\.(com|cn|net|org)\b", " ", sample, flags=re.I)

    terms: list[str] = []
    terms.extend(re.findall(r"#([\w\u4e00-\u9fff]{2,30})#?", sample))
    terms.extend(re.findall(r"《([\w\u4e00-\u9fff]{2,30})》", sample))
    zh_chunks = [
        chunk
        for chunk in re.split(r"[，。！？、；：,.!?:;()\[\]\s/|]+", sample)
        if chunk and _contains_cjk(chunk)
    ]
    terms.extend(zh_chunks)
    terms.extend(re.findall(r"[A-Za-z]{3,24}", sample))

    normalized: list[str] = []
    for term in terms:
        normalized_term = _normalize_topic_token(term)
        if normalized_term:
            normalized.append(normalized_term)
    return normalized


def compute_daily_hot_topics(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_day: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        day = record.get("published_day", "")
        if day:
            by_day.setdefault(day, []).append(record)

    daily_topics: list[dict[str, Any]] = []
    for day, day_records in by_day.items():
        counter: Counter[str] = Counter()
        for record in day_records:
            body = f"{record.get('title', '')} {record.get('text', '')}"
            for term in set(extract_topic_terms(body)):
                counter[term] += 1

        if counter:
            hot_topic, hits = counter.most_common(1)[0]
        else:
            hot_topic, hits = "overall_sentiment", len(day_records)
        daily_topics.append(
            {
                "published_day": day,
                "hot_topic": hot_topic,
                "hot_topic_hits": hits,
                "hot_topic_coverage": round(hits / max(1, len(day_records)), 3),
                "mentions": len(day_records),
            }
        )

    return sorted(daily_topics, key=lambda item: item["published_day"], reverse=True)


def collect_feedback(
    query: str = DEFAULT_QUERY,
    max_items_per_source: int = 30,
    include_news: bool = True,
    include_social: bool = True,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    if include_news:
        records.extend(
            _google_news_feed(
                query=query,
                max_items=max_items_per_source,
                source_kind="news",
                platform="News",
            )
        )

    if include_social:
        social_limit = max(10, max_items_per_source // 2)
        for platform, domain in SOCIAL_DOMAINS.items():
            records.extend(
                _google_news_feed(
                    query=f"({query}) site:{domain}",
                    max_items=social_limit,
                    source_kind="social",
                    platform=platform,
                )
            )
            records.extend(_fetch_apify_platform(platform=platform, query=query, max_items=max_items_per_source))

    return _dedupe(records)


def _snapshot_path(day: date) -> Path:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    return SNAPSHOT_DIR / f"{day.isoformat()}.json"


def load_snapshot(day: date) -> list[dict[str, Any]]:
    path = _snapshot_path(day)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_records_by_day(records: list[dict[str, Any]]) -> list[Path]:
    if not records:
        return []

    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(record["published_day"], []).append(record)

    saved_paths: list[Path] = []
    for day_text, day_records in grouped.items():
        try:
            day = date.fromisoformat(day_text)
        except ValueError:
            continue
        existing = load_snapshot(day)
        merged = _dedupe(existing + day_records)
        path = _snapshot_path(day)
        path.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        saved_paths.append(path)
    return saved_paths


def list_snapshot_days(limit: int = 90) -> list[str]:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    for path in SNAPSHOT_DIR.glob("*.json"):
        try:
            date.fromisoformat(path.stem)
            names.append(path.stem)
        except ValueError:
            continue
    return sorted(names, reverse=True)[:limit]


def load_history(days_back: int = 30) -> list[dict[str, Any]]:
    cutoff = datetime.now(CN_TZ).date() - timedelta(days=days_back)
    records: list[dict[str, Any]] = []
    for day_text in list_snapshot_days(limit=days_back + 7):
        day = date.fromisoformat(day_text)
        if day < cutoff:
            continue
        records.extend(load_snapshot(day))
    return _dedupe(records)


def connector_status() -> list[dict[str, str]]:
    token_exists = bool(os.getenv("APIFY_TOKEN", "").strip())
    statuses: list[dict[str, str]] = [
        {
            "connector": "Google News RSS",
            "type": "News + Mention Discovery",
            "status": "active",
            "detail": "No key required.",
        }
    ]

    for platform, env_name in APIFY_ACTOR_ENV.items():
        actor_id = os.getenv(env_name, "").strip()
        configured = token_exists and bool(actor_id)
        statuses.append(
            {
                "connector": f"{platform} (Apify actor)",
                "type": "Direct social scraping",
                "status": "active" if configured else "optional",
                "detail": (
                    "Configured and ingesting direct platform posts."
                    if configured
                    else f"Set APIFY_TOKEN + {env_name} to enable."
                ),
            }
        )
    return statuses
