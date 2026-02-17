# Open-source Connector Research (GitHub)

This note records connector options reviewed for Shanghai Disney signal collection.

## Repositories reviewed

- `DIYgod/RSSHub` — RSS aggregation framework for many web platforms.
- `JustAnotherArchivist/snscrape` — open social scraping toolkit (X/Twitter and more, availability varies by site changes).
- `dataabc/weibo-crawler` — Weibo crawler implementation.
- `mcxiaoxiao/xiaohongshuCrawler` — Xiaohongshu crawler implementation.
- `linwoodc3/gdeltPyR` and `gdelt/gdelt.github.io` — GDELT open data access.

## What is integrated in this app now

- **Gemini 2.5 Flash + Google Search grounding** as the primary news source.
- **Google News RSS** as lightweight fallback.
- **Optional social mention scan** via Google News `site:` filters.

## Why some GitHub options are not enabled by default

- Platform anti-bot changes can break standalone crawlers quickly.
- Heavy browser automation is not stable on Streamlit free tier.
- A lightweight Google-grounded backend is more reliable for this app’s scope.

## Recommended next step

If deeper social coverage is required, run dedicated crawlers in a separate scheduled backend service and feed normalized JSON into `data/snapshots/`.
