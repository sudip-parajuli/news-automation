# RSS sources for the news poster.
#
# region:
#   "nepal"        -> Nepali-language, general/politics Nepal news
#   "nepal_sports" -> Nepal-focused sports coverage
#   "intl"         -> International news (English, gets translated to Nepali)
#   "intl_sports"  -> International sports (English, gets translated to Nepali)
#   "tech"         -> Technology news (English, gets translated to Nepali)
#
# If a feed URL goes stale or changes, just edit/remove it here -- fetch_news.py
# skips any feed that fails to parse instead of crashing the whole run.

FEEDS = [
    # --- Nepal: general / politics ---
    {"name": "OnlineKhabar", "url": "https://www.onlinekhabar.com/feed", "lang": "ne", "region": "nepal"},
    {"name": "Setopati", "url": "https://www.setopati.com/feed", "lang": "ne", "region": "nepal"},
    {"name": "Ratopati", "url": "https://www.ratopati.com/feed", "lang": "ne", "region": "nepal"},
    {"name": "Nagarik News", "url": "https://nagariknews.nagariknetwork.com/feed", "lang": "ne", "region": "nepal"},
    {"name": "Annapurna Post", "url": "https://www.annapurnapost.com/feed", "lang": "ne", "region": "nepal"},
    {"name": "The Kathmandu Post", "url": "https://kathmandupost.com/rss", "lang": "en", "region": "nepal"},

    # --- International ---
    {"name": "BBC World", "url": "http://feeds.bbci.co.uk/news/world/rss.xml", "lang": "en", "region": "intl"},
    {"name": "BBC Asia", "url": "http://feeds.bbci.co.uk/news/world/asia/rss.xml", "lang": "en", "region": "intl"},
    {"name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml", "lang": "en", "region": "intl"},

    # --- International sports ---
    {"name": "BBC Sport", "url": "http://feeds.bbci.co.uk/sport/rss.xml", "lang": "en", "region": "intl_sports"},

    # --- Technology (drives the new "tech" focus area) ---
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "lang": "en", "region": "tech"},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "lang": "en", "region": "tech"},
    {"name": "Wired", "url": "https://www.wired.com/feed/rss", "lang": "en", "region": "tech"},
]
