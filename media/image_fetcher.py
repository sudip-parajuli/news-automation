import os
import requests
from duckduckgo_search import DDGS
import random

class ImageFetcher:
    def __init__(self, download_dir="storage/temp_images"):
        self.download_dir = download_dir
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)

    def fetch_image(self, query: str, filename: str) -> str:
        """
        Searches and downloads a relevant image from DuckDuckGo.
        Returns the path to the downloaded image.
        """
        save_path = os.path.join(self.download_dir, filename)
        
        # Add 'news' to query to keep it relevant
        search_query = f"{query} news"
        
        try:
            with DDGS() as ddgs:
                results = ddgs.images(
                    keywords=search_query,
                    region="wt-wt",
                    safesearch="on",
                    size="large"
                )
                
                # Filter results for common image extensions
                image_urls = [r['image'] for r in results if r['image'].split('.')[-1].lower() in ['jpg', 'jpeg', 'png']]
                
                if not image_urls:
                    print(f"No images found for query: {query}")
                    return None

                # Try the first few results until one succeeds
                for url in image_urls[:5]:
                    try:
                        response = requests.get(url, timeout=10)
                        if response.status_code == 200:
                            with open(save_path, 'wb') as f:
                                f.write(response.content)
                            print(f"Downloaded image: {save_path}")
                            return save_path
                    except Exception as e:
                        print(f"Failed to download image from {url}: {e}")
        except Exception as e:
            print(f"Image search failed for {query}: {e}")
            
        return None

if __name__ == "__main__":
    fetcher = ImageFetcher()
    fetcher.fetch_image("Japan Earthquake", "test_japan.jpg")
