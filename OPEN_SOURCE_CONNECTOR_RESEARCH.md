# Open-source Connector Research (GitHub)

This note records open-source collection options reviewed for expanding Shanghai Disney signal volume.

## Repositories reviewed

- `DIYgod/RSSHub` — RSS aggregation framework for many web platforms.
- `JustAnotherArchivist/snscrape` — open social scraping toolkit (X/Twitter and more, availability varies by site changes).
- `dataabc/weibo-crawler` — Weibo crawler implementation.
- `mcxiaoxiao/xiaohongshuCrawler` — Xiaohongshu crawler implementation.
- `linwoodc3/gdeltPyR` and `gdelt/gdelt.github.io` — GDELT open data access.

## What is integrated in this app now

- **GDELT Doc API** (`_gdelt_news_feed`) for broader open news coverage.
- **Reddit JSON search** (`_reddit_search_feed`) for global guest chatter.
- **YouTube search RSS** (`_youtube_search_feed`) for global video mentions.
- **Google News RSS + Bing News RSS + DuckDuckGo HTML scraping** for resilient fallback coverage.

## Why some GitHub options are not enabled by default

- Platform anti-bot changes can break standalone crawlers quickly.
- Some repositories require heavy browser automation and are not stable on Streamlit free tier.
- Legal/compliance requirements differ by platform and region.

## Recommended next step

If you need deeper CN social depth, run dedicated crawlers (from vetted open-source repos) in a scheduled backend service and feed normalized JSON into `data/snapshots/`.
