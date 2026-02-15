# Shanghai Disney Guest Pulse Engine

A Streamlit dashboard to monitor how guests feel about their Shanghai Disney trip, with social + news ingestion, sentiment scoring, and day-based navigation.

## What it does

- Tracks mentions from:
  - **Chinese mode (default)**: Xiaohongshu, Douyin, Weibo, Bilibili + broad Shanghai local media
    - Shanghai Observer, Jiefang Daily, Wenhui, Xinmin Evening News, Eastday, Kankanews, Shanghai Daily, Shanghai Gov, and more
  - **English mode (global sources)**: YouTube, X/Twitter, Reddit, Instagram + ABC/CNBC/Reuters/BBC/AP
  - Built-in scraping first: DuckDuckGo HTML + RSS collectors (no API key required)
  - Social/domain discovery via Google News RSS + fallback retry logic
- Scores each post/article as positive / neutral / negative (bilingual keyword model)
- Stores records by day: `data/snapshots/YYYY-MM-DD.json`
- Highlights **one hottest topic per day** (topic hit count + coverage) to reduce information overload
- Adds a **PR Command Center** (risk radar, top outlets, local outlet coverage, recommended actions)
- Keeps each item in **original language + translated version** for bilingual browsing
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

### Bilingual translation

- Uses `deep-translator` (GoogleTranslator backend) for automatic cross-language display.
- If translation is unavailable, the original text is still shown with a fallback message.

## Production ingestion pattern (recommended)

1. Schedule `collect_feedback` every 5-15 minutes (or hourly) via cron/GitHub Actions.
2. Persist daily snapshots.
3. Serve Streamlit dashboard from snapshot files for fast UI response.
4. Keep platform ToS / rate-limit compliance checks enabled.

## Notes

- This project is for public-signal monitoring only.
- Always validate major claims against official channels.
