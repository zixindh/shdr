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
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

CN_TZ = timezone(timedelta(hours=8))
SNAPSHOT_DIR = Path(__file__).resolve().parent / "data" / "snapshots"
DEFAULT_QUERY_CN = "上海迪士尼 游客 体验"
DEFAULT_QUERY_GLOBAL = "Shanghai Disney OR Shanghai Disneyland"
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    )
}

PROFILE_CONFIGS: dict[str, dict[str, Any]] = {
    "cn": {
        "display_name": "Chinese guest mode",
        "news_locale": {"hl": "zh-CN", "gl": "CN", "ceid": "CN:zh-Hans"},
        "social_domains": {
            "Xiaohongshu": "xiaohongshu.com",
            "Douyin": "douyin.com",
            "Weibo": "weibo.com",
            "Bilibili": "bilibili.com",
            "Zhihu": "zhihu.com",
            "Toutiao": "toutiao.com",
            "Tieba": "tieba.baidu.com",
        },
        "news_domains": {
            "Shanghai Observer": "shobserver.com",
            "Jiefang Daily": "jfdaily.com",
            "Wenhui": "whb.cn",
            "Xinmin Evening News": "xinmin.cn",
            "Eastday": "eastday.com",
            "Kankanews": "kankanews.com",
            "Shanghai Daily": "shine.cn",
            "People Shanghai": "sh.people.com.cn",
            "Shanghai Government": "shanghai.gov.cn",
            "SMG": "smg.cn",
            "Xinhua": "news.cn",
            "The Paper": "thepaper.cn",
            "Sina": "sina.com.cn",
            "NBD": "nbd.com.cn",
            "Jiemian": "jiemian.com",
            "Yicai": "yicai.com",
            "Sohu": "sohu.com",
            "163 News": "163.com",
            "Tencent News": "qq.com",
            "China Daily": "chinadaily.com.cn",
        },
        "fallback_news_queries": [
            "上海迪士尼",
            "上海迪士尼 游客",
            "上海迪士尼 乐园 新闻",
            "上海迪士尼 排队",
            "上海迪士尼 服务",
        ],
        "news_domain_scan_limit": 20,
        "local_outlet_names": [
            "Shanghai Observer",
            "Jiefang Daily",
            "Wenhui",
            "Xinmin Evening News",
            "Eastday",
            "Kankanews",
            "Shanghai Daily",
            "People Shanghai",
            "Shanghai Government",
            "SMG",
        ],
        "ddg_region": "cn-zh",
    },
    "global": {
        "display_name": "Global guest mode",
        "news_locale": {"hl": "en-US", "gl": "US", "ceid": "US:en"},
        "social_domains": {
            "YouTube": "youtube.com",
            "X": "x.com",
            "Twitter": "twitter.com",
            "Reddit": "reddit.com",
            "Instagram": "instagram.com",
            "TikTok": "tiktok.com",
            "Facebook": "facebook.com",
            "Threads": "threads.net",
        },
        "news_domains": {
            "ABC": "abcnews.go.com",
            "CNBC": "cnbc.com",
            "Reuters": "reuters.com",
            "BBC": "bbc.com",
            "AP News": "apnews.com",
        },
        "fallback_news_queries": [
            "Shanghai Disney",
            "Shanghai Disneyland",
            "Shanghai Disney Resort news",
        ],
        "news_domain_scan_limit": 10,
        "ddg_region": "us-en",
    },
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
    "bilibili",
    "douyin",
    "park",
    "resort",
    "shanghai",
    "disney",
    "weibo",
    "xiaohongshu",
    "xhs",
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
    "小红书",
    "抖音",
    "微博",
    "哔哩哔哩",
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

RISK_SIGNAL_KEYWORDS: dict[str, list[str]] = {
    "queue_pressure": ["排队", "排队时间", "拥挤", "人多", "堵", "等待", "queue", "crowd", "wait time", "long line"],
    "service_quality": ["服务", "态度", "体验差", "投诉", "维权", "差评", "service", "staff", "complaint", "rude"],
    "ride_reliability": ["故障", "停运", "检修", "卡住", "事故", "延误", "breakdown", "closed", "maintenance", "delay"],
    "pricing_value": ["贵", "太贵", "涨价", "价格", "性价比", "不值", "expensive", "price", "overpriced", "value"],
    "food_safety_cleanliness": ["食品", "卫生", "脏", "异物", "肠胃", "不干净", "food", "hygiene", "dirty", "cleanliness"],
    "transport_entry": ["交通", "地铁", "打车", "入园", "安检", "排队入场", "traffic", "metro", "taxi", "entry", "security check"],
    "weather_ops": ["下雨", "高温", "台风", "雷暴", "天气", "演出取消", "rain", "heat", "storm", "weather", "show cancelled"],
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


def _resolve_secret(key: str, auth_config: dict[str, str] | None = None) -> str:
    if auth_config:
        value = (auth_config.get(key) or "").strip()
        if value:
            return value
    return os.getenv(key, "").strip()


def _build_record(
    source_kind: str,
    platform: str,
    title: str,
    text: str,
    url: str,
    author: str,
    published_at: Any,
    source_profile: str = "cn",
) -> dict[str, Any]:
    published = _safe_parse_dt(published_at)
    published_cn = published.astimezone(CN_TZ)
    body = f"{title}\n{text}".strip()
    sentiment_score, sentiment_label = score_sentiment(body)
    base_id = f"{platform}|{url}|{title}|{published.isoformat()}"

    return {
        "id": hashlib.sha1(base_id.encode("utf-8")).hexdigest(),
        "source_kind": source_kind,
        "source_profile": source_profile,
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


def _google_news_feed(
    query: str,
    max_items: int,
    source_kind: str,
    platform: str,
    locale: dict[str, str] | None = None,
    source_profile: str = "cn",
) -> list[dict[str, Any]]:
    encoded = quote_plus(query)
    urls: list[str] = []
    if locale and locale.get("hl") and locale.get("gl") and locale.get("ceid"):
        urls.append(
            "https://news.google.com/rss/search"
            f"?q={encoded}&hl={quote_plus(locale['hl'])}&gl={quote_plus(locale['gl'])}&ceid={quote_plus(locale['ceid'])}"
        )
    urls.append(f"https://news.google.com/rss/search?q={encoded}")
    records: list[dict[str, Any]] = []

    for url in urls:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            if len(records) >= max_items:
                break
            summary = re.sub(r"<[^>]+>", " ", entry.get("summary", ""))
            record = _build_record(
                source_kind=source_kind,
                source_profile=source_profile,
                platform=platform,
                title=entry.get("title", "").strip(),
                text=re.sub(r"\s+", " ", summary).strip(),
                url=entry.get("link", "").strip(),
                author=_first(entry, ["author", "source"]),
                published_at=entry.get("published") or entry.get("updated"),
            )
            records.append(record)
        if records:
            break
    return records


def _extract_duckduckgo_url(raw_url: str) -> str:
    if not raw_url:
        return ""
    if raw_url.startswith("//"):
        return f"https:{raw_url}"
    if raw_url.startswith("/"):
        parsed = urlparse(f"https://duckduckgo.com{raw_url}")
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(target) if target else ""
    return raw_url


def _duckduckgo_search(query: str, max_items: int, region: str = "") -> list[dict[str, str]]:
    params = {"q": query}
    if region:
        params["kl"] = region
    try:
        response = requests.get(
            "https://duckduckgo.com/html/",
            params=params,
            timeout=30,
            headers=REQUEST_HEADERS,
        )
        response.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    results: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for card in soup.select("div.result"):
        if len(results) >= max_items:
            break
        anchor = card.select_one("a.result__a") or card.select_one("h2 a")
        if anchor is None:
            continue
        url = _extract_duckduckgo_url((anchor.get("href") or "").strip())
        if not url or url in seen_urls:
            continue
        snippet_node = card.select_one(".result__snippet")
        snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""
        title = anchor.get_text(" ", strip=True)
        results.append({"title": title, "text": snippet, "url": url})
        seen_urls.add(url)
    return results


def _collect_domain_mentions_via_search(
    query: str,
    domains: dict[str, str],
    source_kind: str,
    max_items: int,
    source_profile: str,
    region: str,
) -> list[dict[str, Any]]:
    if not domains or max_items <= 0:
        return []

    per_domain = max(2, max_items // max(1, len(domains)))
    records: list[dict[str, Any]] = []
    for platform, domain in domains.items():
        search_results = _duckduckgo_search(
            query=f"({query}) site:{domain}",
            max_items=per_domain,
            region=region,
        )
        for result in search_results:
            records.append(
                _build_record(
                    source_kind=source_kind,
                    source_profile=source_profile,
                    platform=platform,
                    title=result.get("title", ""),
                    text=result.get("text", ""),
                    url=result.get("url", ""),
                    author="DuckDuckGo",
                    published_at=datetime.now(timezone.utc),
                )
            )
    return _dedupe(records)


def _bing_news_feed(
    query: str,
    max_items: int,
    source_profile: str,
) -> list[dict[str, Any]]:
    if max_items <= 0:
        return []
    encoded = quote_plus(query)
    url = f"https://www.bing.com/news/search?q={encoded}&format=RSS"
    feed = feedparser.parse(url)
    records: list[dict[str, Any]] = []
    for entry in feed.entries[:max_items]:
        summary = re.sub(r"<[^>]+>", " ", entry.get("summary", ""))
        records.append(
            _build_record(
                source_kind="news",
                source_profile=source_profile,
                platform=_first(entry, ["source"], "Bing News"),
                title=entry.get("title", "").strip(),
                text=re.sub(r"\s+", " ", summary).strip(),
                url=entry.get("link", "").strip(),
                author=_first(entry, ["author", "source"], "Bing News"),
                published_at=entry.get("published") or entry.get("updated"),
            )
        )
    return records


def _gdelt_news_feed(
    query: str,
    max_items: int,
    source_profile: str,
) -> list[dict[str, Any]]:
    if max_items <= 0:
        return []
    params = {
        "query": query,
        "mode": "ArtList",
        "maxrecords": str(min(250, max_items)),
        "format": "json",
        "sort": "HybridRel",
    }
    try:
        response = requests.get(
            "https://api.gdeltproject.org/api/v2/doc/doc",
            params=params,
            timeout=40,
            headers=REQUEST_HEADERS,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []

    articles = payload.get("articles", []) if isinstance(payload, dict) else []
    records: list[dict[str, Any]] = []
    for article in articles[:max_items]:
        if not isinstance(article, dict):
            continue
        domain = (article.get("domain") or "").strip()
        platform = domain if domain else "GDELT"
        records.append(
            _build_record(
                source_kind="news",
                source_profile=source_profile,
                platform=platform,
                title=(article.get("title") or "").strip(),
                text=(article.get("seendate") or "").strip(),
                url=(article.get("url") or "").strip(),
                author=(article.get("sourcecountry") or "GDELT").strip(),
                published_at=article.get("seendate") or article.get("socialimage") or datetime.now(timezone.utc),
            )
        )
    return records


def _youtube_search_feed(
    query: str,
    max_items: int,
    source_profile: str,
) -> list[dict[str, Any]]:
    if max_items <= 0:
        return []
    encoded = quote_plus(query)
    feed = feedparser.parse(f"https://www.youtube.com/feeds/videos.xml?search_query={encoded}")
    records: list[dict[str, Any]] = []
    for entry in feed.entries[:max_items]:
        summary = re.sub(r"<[^>]+>", " ", entry.get("summary", ""))
        records.append(
            _build_record(
                source_kind="social",
                source_profile=source_profile,
                platform="YouTube",
                title=entry.get("title", "").strip(),
                text=re.sub(r"\s+", " ", summary).strip(),
                url=entry.get("link", "").strip(),
                author=_first(entry, ["author", "yt_author"], "YouTube"),
                published_at=entry.get("published") or entry.get("updated"),
            )
        )
    return records


def _reddit_search_feed(
    query: str,
    max_items: int,
    source_profile: str,
) -> list[dict[str, Any]]:
    if max_items <= 0:
        return []
    params = {
        "q": query,
        "sort": "new",
        "t": "week",
        "limit": str(min(100, max_items)),
    }
    try:
        response = requests.get(
            "https://www.reddit.com/search.json",
            params=params,
            timeout=30,
            headers=REQUEST_HEADERS,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []

    children = (
        payload.get("data", {}).get("children", [])
        if isinstance(payload, dict)
        else []
    )
    records: list[dict[str, Any]] = []
    for child in children[:max_items]:
        item = child.get("data", {}) if isinstance(child, dict) else {}
        permalink = (item.get("permalink") or "").strip()
        url = f"https://www.reddit.com{permalink}" if permalink else (item.get("url") or "").strip()
        subreddit = (item.get("subreddit_name_prefixed") or "Reddit").strip()
        records.append(
            _build_record(
                source_kind="social",
                source_profile=source_profile,
                platform="Reddit",
                title=(item.get("title") or "").strip(),
                text=(item.get("selftext") or "").strip(),
                url=url,
                author=subreddit,
                published_at=item.get("created_utc"),
            )
        )
    return records


def _run_apify_actor(actor_id: str, token: str, actor_input: dict[str, Any]) -> list[dict[str, Any]]:
    run_url = (
        f"https://api.apify.com/v2/acts/{actor_id}/runs"
        f"?token={token}&waitForFinish=45"
    )
    try:
        run_response = requests.post(run_url, json=actor_input, timeout=60, headers=REQUEST_HEADERS)
        run_response.raise_for_status()
        run_json = run_response.json().get("data", {})
        dataset_id = run_json.get("defaultDatasetId")
        if not dataset_id:
            return []

        data_url = (
            f"https://api.apify.com/v2/datasets/{dataset_id}/items"
            f"?token={token}&clean=true&format=json"
        )
        data_response = requests.get(data_url, timeout=60, headers=REQUEST_HEADERS)
        data_response.raise_for_status()
        items = data_response.json()
        return items if isinstance(items, list) else []
    except Exception:
        return []


def _fetch_apify_platform(
    platform: str,
    query: str,
    max_items: int,
    source_profile: str = "cn",
    auth_config: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    token = _resolve_secret("APIFY_TOKEN", auth_config)
    actor_env = APIFY_ACTOR_ENV.get(platform)
    actor_id = _resolve_secret(actor_env, auth_config) if actor_env else ""
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
                source_profile=source_profile,
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


def _get_profile_config(source_profile: str) -> dict[str, Any]:
    return PROFILE_CONFIGS.get(source_profile, PROFILE_CONFIGS["cn"])


def _collect_profile_news(
    query: str,
    max_items: int,
    source_profile: str,
) -> list[dict[str, Any]]:
    config = _get_profile_config(source_profile)
    locale = config["news_locale"]
    region = config.get("ddg_region", "")
    all_domains = list(config["news_domains"].items())
    scan_limit = min(len(all_domains), int(config.get("news_domain_scan_limit", len(all_domains))))
    selected_domains = all_domains[:scan_limit]
    domain_limit = max(3, max_items // max(3, scan_limit))
    query_candidates = [query] + [
        text for text in config["fallback_news_queries"] if text.strip().lower() != query.strip().lower()
    ]

    records: list[dict[str, Any]] = []
    for idx, candidate in enumerate(query_candidates[:3]):
        per_query_limit = max_items if idx == 0 else max(8, max_items // 3)
        records.extend(
            _google_news_feed(
                query=candidate,
                max_items=per_query_limit,
                source_kind="news",
                platform="News",
                locale=locale,
                source_profile=source_profile,
            )
        )

    for outlet, domain in selected_domains:
        records.extend(
            _google_news_feed(
                query=f"({query}) site:{domain}",
                max_items=domain_limit,
                source_kind="news",
                platform=outlet,
                locale=locale,
                source_profile=source_profile,
            )
        )

    records.extend(_bing_news_feed(query=query, max_items=max(6, max_items // 2), source_profile=source_profile))
    records.extend(_gdelt_news_feed(query=query, max_items=max(20, max_items), source_profile=source_profile))
    records.extend(
        _collect_domain_mentions_via_search(
            query=query,
            domains=dict(selected_domains),
            source_kind="news",
            max_items=max_items,
            source_profile=source_profile,
            region=region,
        )
    )

    # If localized feed returns nothing, retry with locale-agnostic URL.
    if not records:
        records.extend(
            _google_news_feed(
                query=query,
                max_items=max_items,
                source_kind="news",
                platform="News",
                locale=None,
                source_profile=source_profile,
            )
        )

    return _dedupe(records)


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


def _record_body(record: dict[str, Any]) -> str:
    return f"{record.get('title', '')} {record.get('text', '')}".lower()


def compute_media_brief(records: list[dict[str, Any]], source_profile: str = "cn") -> dict[str, Any]:
    config = _get_profile_config(source_profile)
    news_records = [item for item in records if item.get("source_kind") == "news"]
    social_records = [item for item in records if item.get("source_kind") == "social"]
    negative_records = [item for item in records if item.get("sentiment_label") == "negative"]

    risk_rows: list[dict[str, Any]] = []
    for risk_key, terms in RISK_SIGNAL_KEYWORDS.items():
        hits = 0
        negative_hits = 0
        for item in records:
            body = _record_body(item)
            if any(term.lower() in body for term in terms):
                hits += 1
                if item.get("sentiment_label") == "negative":
                    negative_hits += 1
        if hits == 0:
            continue
        neg_ratio = negative_hits / hits
        risk_rows.append(
            {
                "risk_key": risk_key,
                "mentions": hits,
                "negative_mentions": negative_hits,
                "negative_ratio": round(neg_ratio, 3),
                "risk_score": round(hits * (1 + neg_ratio), 2),
            }
        )
    risk_rows.sort(key=lambda item: (item["risk_score"], item["mentions"]), reverse=True)

    outlet_counter: Counter[str] = Counter()
    outlet_sentiment: dict[str, list[float]] = {}
    for item in news_records:
        outlet = item.get("platform", "Unknown")
        outlet_counter[outlet] += 1
        outlet_sentiment.setdefault(outlet, []).append(float(item.get("sentiment_score", 0)))

    top_outlets: list[dict[str, Any]] = []
    for outlet, mentions in outlet_counter.most_common(12):
        scores = outlet_sentiment.get(outlet, [0.0])
        top_outlets.append(
            {
                "outlet": outlet,
                "mentions": mentions,
                "avg_sentiment": round(sum(scores) / max(1, len(scores)), 3),
            }
        )

    local_outlet_seed = config.get("local_outlet_names") or list(config.get("news_domains", {}).keys())[:6]
    local_outlets = set(local_outlet_seed)
    local_hits = sorted(outlet for outlet in outlet_counter if outlet in local_outlets)
    local_coverage = 0.0 if not local_outlets else len(local_hits) / len(local_outlets)

    actions: list[str] = []
    is_cn = source_profile == "cn"

    def action_text(cn: str, en: str) -> str:
        return cn if is_cn else en

    top_risks = risk_rows[:3]
    for risk in top_risks:
        key = risk["risk_key"]
        if key == "queue_pressure":
            actions.append(
                action_text(
                    "排队压力较高：建议加强等候时长透明发布与分流引导话术。",
                    "Queue pressure is high: push wait-time transparency and crowd dispersal messaging.",
                )
            )
        elif key == "ride_reliability":
            actions.append(
                action_text(
                    "设备稳定性风险：快速发布检修状态和恢复时间预估。",
                    "Ride reliability issue: publish maintenance status updates and recovery timelines quickly.",
                )
            )
        elif key == "service_quality":
            actions.append(
                action_text(
                    "服务体验风险：先回应投诉，再同步一线服务改进说明。",
                    "Service quality concern: acknowledge complaints and issue frontline service improvement brief.",
                )
            )
        elif key == "pricing_value":
            actions.append(
                action_text(
                    "价格感知偏弱：强化套餐价值表达并给出游客受益示例。",
                    "Pricing sentiment is weak: reinforce bundled value messaging and guest-benefit examples.",
                )
            )
        elif key == "food_safety_cleanliness":
            actions.append(
                action_text(
                    "餐饮/卫生风险出现：建议发布卫生保障说明和整改动作。",
                    "Food/cleanliness risk detected: release hygiene assurance statement and corrective actions.",
                )
            )
        elif key == "transport_entry":
            actions.append(
                action_text(
                    "入园与交通摩擦上升：补充到达指引和分时入园建议。",
                    "Entry/transport friction: provide arrival guidance and entry time-window recommendations.",
                )
            )
        elif key == "weather_ops":
            actions.append(
                action_text(
                    "天气扰动风险：提前发布替代方案与补偿政策说明。",
                    "Weather disruption risk: post proactive operation alternatives and compensation policies.",
                )
            )

    if source_profile == "cn" and local_coverage < 0.4:
        actions.append("上海本地媒体覆盖偏薄：建议主动向本地编辑推送核实后的更新。")
    if not actions:
        actions.append(
            action_text(
                "舆情整体稳定：保持主动更新并放大正向游客故事。",
                "Narrative is stable: keep proactive updates and amplify positive guest stories.",
            )
        )

    return {
        "total_mentions": len(records),
        "news_mentions": len(news_records),
        "social_mentions": len(social_records),
        "negative_mentions": len(negative_records),
        "local_outlet_coverage": round(local_coverage, 3),
        "local_outlets_hit": local_hits,
        "risk_table": risk_rows,
        "top_outlets": top_outlets,
        "actions": actions[:5],
    }


def collect_feedback(
    query: str = DEFAULT_QUERY_CN,
    max_items_per_source: int = 30,
    include_news: bool = True,
    include_social: bool = True,
    source_profile: str = "cn",
    auth_config: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    config = _get_profile_config(source_profile)
    locale = config["news_locale"]
    region = config.get("ddg_region", "")
    social_domains = config["social_domains"]

    if include_news:
        records.extend(_collect_profile_news(query=query, max_items=max_items_per_source, source_profile=source_profile))

    if include_social:
        social_limit = max(10, max_items_per_source // 2)
        for platform, domain in social_domains.items():
            records.extend(
                _google_news_feed(
                    query=f"({query}) site:{domain}",
                    max_items=social_limit,
                    source_kind="social",
                    platform=platform,
                    locale=locale,
                    source_profile=source_profile,
                )
            )
            if source_profile == "cn":
                records.extend(
                    _fetch_apify_platform(
                        platform=platform,
                        query=query,
                        max_items=max_items_per_source,
                        source_profile=source_profile,
                        auth_config=auth_config,
                    )
                )
        if source_profile == "global":
            records.extend(_reddit_search_feed(query=query, max_items=max_items_per_source, source_profile=source_profile))
            records.extend(_youtube_search_feed(query=query, max_items=max_items_per_source, source_profile=source_profile))
        records.extend(
            _collect_domain_mentions_via_search(
                query=query,
                domains=social_domains,
                source_kind="social",
                max_items=max_items_per_source,
                source_profile=source_profile,
                region=region,
            )
        )

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


def connector_status(
    source_profile: str = "cn",
    auth_config: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    config = _get_profile_config(source_profile)
    token_exists = bool(_resolve_secret("APIFY_TOKEN", auth_config))
    all_domains = list(config["news_domains"].items())
    scan_limit = min(len(all_domains), int(config.get("news_domain_scan_limit", len(all_domains))))
    statuses: list[dict[str, str]] = [
        {
            "connector": "Source profile",
            "type": "Routing mode",
            "status": source_profile,
            "detail": f"{config['display_name']} | scanning {scan_limit}/{len(all_domains)} news outlets per refresh",
        },
        {
            "connector": "Google News RSS",
            "type": "News + Mention Discovery",
            "status": "active",
            "detail": "No key required.",
        },
        {
            "connector": "Bing News RSS",
            "type": "News fallback",
            "status": "active",
            "detail": "No key required.",
        },
        {
            "connector": "GDELT Doc API",
            "type": "Open news API",
            "status": "active",
            "detail": "No key required.",
        },
        {
            "connector": "DuckDuckGo HTML",
            "type": "Direct web scraping",
            "status": "active",
            "detail": "No key required.",
        },
    ]

    for outlet, domain in all_domains:
        statuses.append(
            {
                "connector": outlet,
                "type": "News outlet",
                "status": "active" if outlet in dict(all_domains[:scan_limit]) else "standby",
                "detail": f"site:{domain}",
            }
        )

    for platform, domain in config["social_domains"].items():
        statuses.append(
            {
                "connector": platform,
                "type": "Social discovery",
                "status": "active",
                "detail": f"site:{domain}",
            }
        )

    if source_profile == "global":
        statuses.append(
            {
                "connector": "Reddit JSON Search",
                "type": "Open social API",
                "status": "active",
                "detail": "No key required.",
            }
        )
        statuses.append(
            {
                "connector": "YouTube Search RSS",
                "type": "Open social feed",
                "status": "active",
                "detail": "No key required.",
            }
        )

    if source_profile != "cn":
        return statuses

    for platform, env_name in APIFY_ACTOR_ENV.items():
        actor_id = _resolve_secret(env_name, auth_config)
        configured = token_exists and bool(actor_id) and platform in config["social_domains"]
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
