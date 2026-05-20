from __future__ import annotations

from urllib.parse import quote_plus
import feedparser


def google_news_rss(query: str, limit: int = 5):
    url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(url)
    results = []
    for entry in feed.entries[:limit]:
        results.append(
            {
                "source": "GOOGLE_NEWS",
                "company": query,
                "title": getattr(entry, "title", ""),
                "published_at": getattr(entry, "published", ""),
                "url": getattr(entry, "link", ""),
                "raw": {
                    "summary": getattr(entry, "summary", ""),
                    "query": query,
                },
            }
        )
    return results
