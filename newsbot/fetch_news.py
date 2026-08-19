import time

import feedparser

from . import config
from .rss_sources import FEEDS

SPORTS_KEYWORDS = [
    "cricket", "football", "soccer", "volleyball", "kabaddi", "sport", "sports",
    "olympic", "sea games", "anfa", "psl", "ipl", "world cup", "worldcup",
    "क्रिकेट", "फुटबल", "खेल", "खेलकुद", "भलिबल", "ओलम्पिक",
]

POLITICS_KEYWORDS = [
    "parliament", "minister", "election", "government", "prime minister", "party",
    "cabinet", "politic", "president", "congress", "vote",
    "संसद", "मन्त्री", "सरकार", "निर्वाचन", "राजनीति", "प्रधानमन्त्री", "पार्टी", "मन्त्रिपरिषद",
]

TECH_KEYWORDS = [
    "technology", "tech ", "artificial intelligence", " ai ", "smartphone", "startup",
    "software", "gadget", "iphone", "android", "chatgpt", "openai", "app store",
    "प्रविधि", "एआई", "स्मार्टफोन", "एप",
]

VIRAL_KEYWORDS = [
    "viral", "trending", "goes viral", "internet reacts", "social media reacts",
    "भाइरल", "ट्रेन्डिङ",
]

FAKE_NEWS_KEYWORDS = [
    "fake news", "misinformation", "disinformation", "hoax", "fact check", "fact-check", "debunk",
    "भ्रामक", "फेक न्युज", "हल्ला", "तथ्याङ्क जाँच",
]


def classify(title, summary, region=None):
    text = f"{title} {summary}".lower()
    if region == "tech" or any(k in text for k in TECH_KEYWORDS):
        return "tech"
    if any(k in text for k in FAKE_NEWS_KEYWORDS):
        return "fake_news"
    if any(k in text for k in VIRAL_KEYWORDS):
        return "viral"
    if any(k in text for k in SPORTS_KEYWORDS):
        return "sports"
    if any(k in text for k in POLITICS_KEYWORDS):
        return "politics"
    return "general"


def fetch_all(max_age_hours=None):
    max_age_hours = max_age_hours or config.MAX_ITEM_AGE_HOURS
    cutoff = time.time() - max_age_hours * 3600
    items = []

    for feed in FEEDS:
        try:
            parsed = feedparser.parse(feed["url"])
            if getattr(parsed, "bozo", 0) and not parsed.entries:
                print(f"[fetch_news] {feed['name']}: no entries parsed, skipping")
                continue
            for entry in parsed.entries:
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                ts = time.mktime(published) if published else time.time()
                if ts < cutoff:
                    continue

                title = (entry.get("title") or "").strip()
                summary = (entry.get("summary") or entry.get("description") or "").strip()
                link = (entry.get("link") or "").strip()
                if not title or not link:
                    continue

                items.append({
                    "source": feed["name"],
                    "lang": feed["lang"],
                    "region": feed["region"],
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "published_ts": ts,
                    "category": classify(title, summary, feed["region"]),
                })
        except Exception as exc:  # noqa: BLE001 - one bad feed must not kill the run
            print(f"[fetch_news] Failed to fetch {feed['name']}: {exc}")

    return items
