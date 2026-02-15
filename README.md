# Shanghai Disney Guest Pulse Engine

A Streamlit dashboard to monitor how guests feel about their Shanghai Disney trip, with social + news ingestion, sentiment scoring, and day-based navigation.

## What it does

- Tracks mentions from:
  - **Chinese mode (default)**: Xiaohongshu, Douyin, Weibo, Bilibili + broad Shanghai local media
    - Shanghai Observer, Jiefang Daily, Wenhui, Xinmin Evening News, Eastday, Kankanews, Shanghai Daily, Shanghai Gov, and more
  - **English mode (global sources)**: YouTube, X/Twitter, Reddit, Instagram + ABC/CNBC/Reuters/BBC/AP
  - Built-in scraping first: DuckDuckGo HTML + RSS collectors + GDELT + Reddit JSON + YouTube RSS (no API key required)
  - Social/domain discovery via Google News RSS + fallback retry logic
- Scores each post/article as positive / neutral / negative (CN+EN keyword model)
- Stores records by day: `data/snapshots/YYYY-MM-DD.json`
- Highlights **one hottest topic per day** (topic hit count + coverage) to reduce information overload
- Adds a **Media Intelligence cockpit** (risk radar, top outlets, local outlet coverage, recommended actions)
- Single-language display mode:
  - Choose **中文** or **English**
  - UI and content are rendered in the selected language
- Supports update modes:
  - Near real-time (5-minute auto-refresh)
  - Daily snapshot (24-hour refresh)
  - Manual refresh
- Includes an optional Gemini summary for selected day (`gemini-2.5-flash`)
- Automatically stores source profile (`cn` / `global`) with each record

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Optional environment variables

### AI summary

- `GEMINI_API_KEY`
- Or input Gemini key directly in the Streamlit sidebar (session-only)

### Direct social scraping (recommended for production)

- `APIFY_TOKEN`
- `APIFY_XHS_ACTOR_ID`
- `APIFY_DOUYIN_ACTOR_ID`
- `APIFY_WEIBO_ACTOR_ID`

If Apify is not configured, the app still runs using RSS-based social mention discovery + news ingestion.
If Apify is configured (sidebar input or env), the app performs deeper direct social scraping in Chinese mode.

### Single-language display translation

- Uses `deep-translator` (GoogleTranslator backend) only when source content is in a different language than current display mode.
- If translation is unavailable, the original text is shown.

## Production ingestion pattern (recommended)

1. Schedule `collect_feedback` every 5-15 minutes (or hourly) via cron/GitHub Actions.
2. Persist daily snapshots.
3. Serve Streamlit dashboard from snapshot files for fast UI response.
4. Keep platform ToS / rate-limit compliance checks enabled.

## Code reference map

- `app.py`
  - Streamlit UI, language/source mode switch, daily navigation, media intelligence panels
  - Optional session-only API key inputs (Gemini / Apify)
- `feedback_engine.py`
  - Source profiles (`cn` / `global`) and outlet/domain configuration
  - Collection pipeline (RSS + search scraping + GDELT + optional Apify + global social open endpoints)
  - Daily topic extraction and media-risk summarization (`compute_media_brief`)
  - Snapshot persistence and connector status reporting

## Open-source connector research

See `OPEN_SOURCE_CONNECTOR_RESEARCH.md` for GitHub research and integration decisions.

## Notes

- This project is for public-signal monitoring only.
- Always validate major claims against official channels.
