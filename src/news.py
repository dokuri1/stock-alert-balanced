from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus
import feedparser


def _entry_published_iso(entry) -> str:
    if getattr(entry, "published_parsed", None):
        dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        return dt.isoformat()
    return ""


def google_news_rss(query: str, limit: int = 5, max_age_hours: int = 36):
    url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(url)
    results = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

    for entry in feed.entries:
        published_iso = _entry_published_iso(entry)
        if published_iso:
            try:
                published_dt = datetime.fromisoformat(published_iso)
                if published_dt < cutoff:
                    continue
            except Exception:
                pass

        results.append(
            {
                "source": "GOOGLE_NEWS",
                "company": query,
                "title": getattr(entry, "title", ""),
                "published_at": published_iso or getattr(entry, "published", ""),
                "url": getattr(entry, "link", ""),
                "raw": {
                    "summary": getattr(entry, "summary", ""),
                    "query": query,
                },
            }
        )
        if len(results) >= limit:
            break
    return results
