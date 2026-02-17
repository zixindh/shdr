# Shanghai Disney Guest Pulse Engine

A Streamlit dashboard for Shanghai Disney public-signal monitoring with a **Gemini-first, Google-grounded** news pipeline.

## What it does

- Uses **Gemini 2.5 Flash + Google Search grounding** as the primary news source.
- Collects both **English and Chinese** news every refresh.
- Keeps backend lightweight:
  - Primary: Gemini grounded search
  - Fallback: Google News RSS only
  - Optional social mention scan: Google News `site:` filters (lightweight)
- Scores each item as positive / neutral / negative (CN+EN keyword model).
- Stores records by day: `data/snapshots/YYYY-MM-DD.json`.
- Surfaces one hot topic per day plus media-risk summaries.

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Required config

- `GEMINI_API_KEY` (env var or sidebar input)

Without a Gemini key, the app still runs using Google News RSS fallback, but Gemini grounding is disabled.

## Google Search grounding activation (official pattern)

Google docs pattern used by this project:

```python
from google import genai
from google.genai import types

client = genai.Client(api_key="YOUR_KEY")
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Your prompt",
    config=types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())]
    ),
)
```

Reference: https://ai.google.dev/gemini-api/docs/grounding

## Notes

- Translation UI uses `deep-translator` only when needed.
- This project is for public-signal monitoring only.
- Validate critical claims with official channels.
