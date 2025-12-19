import feedparser
import hashlib
import time
from datetime import datetime
from typing import List, Dict

class RSSFetcher:
    def __init__(self, feeds: List[str]):
        self.feeds = feeds

    def fetch_all(self) -> List[Dict]:
        all_news = []
        for url in self.feeds:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries:
                    news_item = {
                        "headline": entry.get("title", ""),
                        "content": entry.get("summary", "") or entry.get("description", ""),
                        "source": url,
                        "published_time": entry.get("published", ""),
                        "url": entry.get("link", "")
                    }
                    news_item["hash"] = self._generate_hash(news_item)
                    all_news.append(news_item)
            except Exception as e:
                print(f"Error fetching {url}: {e}")
        return all_news

    def _generate_hash(self, item: Dict) -> str:
        content = f"{item['headline']}{item['content']}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

if __name__ == "__main__":
    # Example usage
    feeds = [
        "http://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www.reutersagency.com/feed/?best-topics=world-news&post_type=best",
        "https://feeds.aljazeera.com/rss/world",
        "https://www.thehindu.com/news/international/feeder/default.rss"
    ]
    fetcher = RSSFetcher(feeds)
    news = fetcher.fetch_all()
    print(f"Fetched {len(news)} items.")
    if news:
        print(f"First item: {news[0]['headline']}")
