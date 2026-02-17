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
from dateutil import parser as date_parser
from google import genai
from google.genai import types

CN_TZ = timezone(timedelta(hours=8))
SNAPSHOT_DIR = Path(__file__).resolve().parent / "data" / "snapshots"
DEFAULT_QUERY_CN = "上海迪士尼 游客 体验"
DEFAULT_QUERY_GLOBAL = "Shanghai Disney OR Shanghai Disneyland"
GEMINI_NEWS_MODEL = os.getenv("GEMINI_NEWS_MODEL", "gemini-2.5-flash")
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
    },
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


def _init_gemini_client(auth_config: dict[str, str] | None = None) -> genai.Client | None:
    api_key = _resolve_secret("GEMINI_API_KEY", auth_config)
    if not api_key:
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception:
        return None


def _extract_json_payload(raw_text: str) -> Any:
    text = (raw_text or "").strip()
    if not text:
        return {}

    # Gemini may wrap JSON in markdown fences; strip them first.
    fence_match = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", text, flags=re.I | re.S)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    candidates: list[str] = []
    first_obj, last_obj = text.find("{"), text.rfind("}")
    if first_obj != -1 and last_obj > first_obj:
        candidates.append(text[first_obj : last_obj + 1])
    first_arr, last_arr = text.find("["), text.rfind("]")
    if first_arr != -1 and last_arr > first_arr:
        candidates.append(text[first_arr : last_arr + 1])

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except Exception:
            continue
    return {}


def _payload_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "news", "articles", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _gemini_grounded_news_for_language(
    client: genai.Client,
    query: str,
    max_items: int,
    language_name: str,
    language_code: str,
    source_profile: str,
) -> list[dict[str, Any]]:
    prompt = (
        "You are a news collector for Shanghai Disney market monitoring.\n"
        "Use Google Search grounding to find recent trustworthy NEWS articles only.\n"
        f"Target language for article selection: {language_name}.\n"
        f"Topic: {query}\n"
        f"Return up to {max_items} results.\n"
        "Output JSON only (no markdown) in this shape:\n"
        "{\n"
        '  "items": [\n'
        '    {\n'
        '      "title": "string",\n'
        '      "summary": "string",\n'
        '      "url": "https://...",\n'
        '      "source": "publisher name",\n'
        '      "published_at": "ISO-8601 date or datetime",\n'
        '      "language": "en or zh"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Rules:\n"
        "- Prefer established media/news outlets.\n"
        "- Exclude social posts, forums, and low-trust sources.\n"
        "- Keep summaries concise."
    )
    try:
        response = client.models.generate_content(
            model=GEMINI_NEWS_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )
    except Exception:
        return []

    response_text = (getattr(response, "text", "") or "").strip()
    if not response_text:
        try:
            parts = response.candidates[0].content.parts
            response_text = "\n".join(
                part.text for part in parts if hasattr(part, "text") and (part.text or "").strip()
            ).strip()
        except Exception:
            response_text = ""
    if not response_text:
        return []

    payload = _extract_json_payload(response_text)
    items = _payload_items(payload)
    records: list[dict[str, Any]] = []

    for item in items:
        title = _first(item, ["title", "headline"])
        summary = _first(item, ["summary", "snippet", "description"])
        url = _first(item, ["url", "link"])
        source = _first(item, ["source", "publisher", "outlet"], default=f"Google News ({language_code})")
        published_at = _first(item, ["published_at", "publishedAt", "date", "datetime"])
        if not title and not summary:
            continue
        if not url:
            continue

        item_language = _first(item, ["language", "lang"]).lower()
        if item_language not in {"en", "zh"}:
            item_language = detect_language(f"{title} {summary}")
        if item_language == "unknown":
            item_language = language_code
        if item_language != language_code:
            continue

        records.append(
            _build_record(
                source_kind="news",
                source_profile=source_profile,
                platform=source,
                title=title,
                text=summary,
                url=url,
                author="Gemini Grounded Search",
                published_at=published_at or datetime.now(timezone.utc),
            )
        )
        if len(records) >= max_items:
            break
    return records


def _google_news_bilingual_fallback(
    query: str,
    max_items: int,
    source_profile: str,
) -> list[dict[str, Any]]:
    if max_items <= 0:
        return []

    unique_queries: list[str] = []
    for candidate in [query, DEFAULT_QUERY_GLOBAL, DEFAULT_QUERY_CN]:
        cleaned = (candidate or "").strip()
        if cleaned and cleaned.lower() not in {item.lower() for item in unique_queries}:
            unique_queries.append(cleaned)

    locale_cn = PROFILE_CONFIGS["cn"]["news_locale"]
    locale_en = PROFILE_CONFIGS["global"]["news_locale"]
    locale_primary = _get_profile_config(source_profile)["news_locale"]
    locales = [locale_primary, locale_en, locale_cn, None]

    records: list[dict[str, Any]] = []
    per_pull = max(4, max_items // 2)
    for candidate in unique_queries[:3]:
        for locale in locales:
            records.extend(
                _google_news_feed(
                    query=candidate,
                    max_items=per_pull,
                    source_kind="news",
                    platform="Google News RSS",
                    locale=locale,
                    source_profile=source_profile,
                )
            )
            deduped = _dedupe(records)
            if len(deduped) >= max_items:
                return deduped[:max_items]
    return _dedupe(records)[:max_items]


def _gemini_grounded_news(
    query: str,
    max_items: int,
    source_profile: str,
    auth_config: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    client = _init_gemini_client(auth_config)
    if client is None or max_items <= 0:
        return []

    per_language = max(4, (max_items + 1) // 2)
    records: list[dict[str, Any]] = []
    records.extend(
        _gemini_grounded_news_for_language(
            client=client,
            query=query,
            max_items=per_language,
            language_name="English",
            language_code="en",
            source_profile=source_profile,
        )
    )
    records.extend(
        _gemini_grounded_news_for_language(
            client=client,
            query=query,
            max_items=per_language,
            language_name="Chinese",
            language_code="zh",
            source_profile=source_profile,
        )
    )
    return _dedupe(records)


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
    auth_config: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    records = _gemini_grounded_news(
        query=query,
        max_items=max_items,
        source_profile=source_profile,
        auth_config=auth_config,
    )
    min_expected = max(6, max_items // 2)
    if len(records) >= min_expected:
        return records[:max_items]

    # Keep the fallback lightweight and Google-native.
    records.extend(
        _google_news_bilingual_fallback(
            query=query,
            max_items=max_items,
            source_profile=source_profile,
        )
    )
    return _dedupe(records)[:max_items]


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
    social_domains = config["social_domains"]

    if include_news:
        records.extend(
            _collect_profile_news(
                query=query,
                max_items=max_items_per_source,
                source_profile=source_profile,
                auth_config=auth_config,
            )
        )

    if include_social:
        social_limit = max(4, max_items_per_source // 3)
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
    gemini_ready = bool(_resolve_secret("GEMINI_API_KEY", auth_config))
    statuses: list[dict[str, str]] = [
        {
            "connector": "Source profile",
            "type": "Routing mode",
            "status": source_profile,
            "detail": f"{config['display_name']} | bilingual EN+ZH news collection",
        },
        {
            "connector": "Gemini + Google Search",
            "type": "Primary grounded news source",
            "status": "active" if gemini_ready else "optional",
            "detail": (
                "Grounded search is enabled for both English and Chinese news."
                if gemini_ready
                else "Set GEMINI_API_KEY to enable grounded Google Search collection."
            ),
        },
        {
            "connector": "Google News RSS",
            "type": "Lightweight fallback",
            "status": "active",
            "detail": "Used only when Gemini-grounded output is unavailable or insufficient.",
        },
    ]

    for platform, domain in config["social_domains"].items():
        statuses.append(
            {
                "connector": platform,
                "type": "Optional social mention scan",
                "status": "standby",
                "detail": f"Google News site filter: site:{domain}",
            }
        )
    return statuses
