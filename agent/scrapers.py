import logging
import feedparser
import requests
from pytrends.request import TrendReq
from models.schemas import TrendData

logger = logging.getLogger(__name__)

TARGET_KEYWORDS = [
    "data analytics", "machine learning", "artificial intelligence", "automation",
    "career growth", "startup", "python", "llm", "generative ai", "data science",
    "business intelligence", "saas", "founder", "product management",
]


def _fetch_google_trends() -> list[TrendData]:
    try:
        pt = TrendReq(hl="en-IN", tz=330, timeout=(10, 25))
        pt.build_payload(kw_list=["data analytics", "AI automation", "career growth"], geo="IN", timeframe="now 1-d")
        related = pt.related_queries()
        topics: list[TrendData] = []
        for kw, data in related.items():
            if data.get("top") is not None:
                for _, row in data["top"].head(3).iterrows():
                    topics.append(TrendData(topic=row["query"], source="google", score=float(row["value"]) / 100))
        trending_searches = pt.trending_searches(pn="india")
        for term in trending_searches[0].head(5).tolist():
            topics.append(TrendData(topic=str(term), source="google", score=0.5))
        return topics
    except Exception as e:
        logger.warning("Google Trends fetch failed: %s", e)
        return []


def _fetch_rss_trends(feed_urls: list[str]) -> list[TrendData]:
    topics: list[TrendData] = []
    for url in feed_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                title = entry.get("title", "").strip()
                if title:
                    topics.append(TrendData(topic=title, source="rss", score=0.4, context=entry.get("summary", "")[:200]))
        except Exception as e:
            logger.warning("RSS fetch failed for %s: %s", url, e)
    return topics


def fetch_all_trends(rss_feeds: list[str] | None = None) -> list[TrendData]:
    from config.settings import settings
    feeds = rss_feeds or settings.rss_feed_list
    google = _fetch_google_trends()
    rss = _fetch_rss_trends(feeds)
    return google + rss
