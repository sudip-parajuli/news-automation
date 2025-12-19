from duckduckgo_search import DDGS
import hashlib
from typing import List, Dict

class DDGFetcher:
    def __init__(self):
        self.ddgs = DDGS()

    def fetch_latest_news(self, query: str = "international breaking news", limit: int = 5) -> List[Dict]:
        """
        Fetches latest news using DuckDuckGo search.
        """
        all_news = []
        try:
            results = list(self.ddgs.news(query, max_results=limit))
            for r in results:
                news_item = {
                    "headline": r.get("title", ""),
                    "content": r.get("body", ""),
                    "source": r.get("source", "DuckDuckGo"),
                    "published_time": r.get("date", ""),
                    "url": r.get("url", "")
                }
                news_item["hash"] = hashlib.sha256(f"{news_item['headline']}{news_item['content']}".encode('utf-8')).hexdigest()
                all_news.append(news_item)
        except Exception as e:
            print(f"Error fetching from DDG: {e}")
        return all_news

if __name__ == "__main__":
    fetcher = DDGFetcher()
    news = fetcher.fetch_latest_news()
    print(f"Fetched {len(news)} items from DDG.")
