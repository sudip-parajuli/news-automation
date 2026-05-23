import httpx
import random
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
from scripts.llm_utils import call_gemini

load_dotenv()

class TopicGenerator:
    def __init__(self):
        self.subreddits = ["technology", "economics", "worldnews", "futurology"]
        self.rss_feeds = [
            "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US",
            "https://feeds.bbci.co.uk/news/world/rss.xml"
        ]

    def get_trending_topic(self) -> str:
        headlines = []

        # Try Reddit
        subreddit = random.choice(self.subreddits)
        try:
            url = f"https://www.reddit.com/r/{subreddit}/top.json?limit=5&t=day"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NewsTrendingToday/1.0"}
            response = httpx.get(url, headers=headers, timeout=15.0)
            if response.status_code == 200:
                data = response.json()
                for child in data.get("data", {}).get("children", []):
                    title = child.get("data", {}).get("title")
                    if title:
                        headlines.append(title)
        except Exception as e:
            print(f"Reddit topic fetch failed: {e}")

        # Try RSS if Reddit failed or just to add more
        if len(headlines) < 3:
            feed = random.choice(self.rss_feeds)
            try:
                response = httpx.get(feed, timeout=15.0)
                if response.status_code == 200:
                    root = ET.fromstring(response.text)
                    for item in root.findall(".//item")[:5]:
                        title = item.find("title")
                        if title is not None and title.text:
                            headlines.append(title.text)
            except Exception as e:
                print(f"RSS topic fetch failed: {e}")

        if not headlines:
            headlines = [
                "The surprising economics of the global semiconductor shortage",
                "Why the population collapse is happening faster than expected",
                "The hidden cost of green energy transition"
            ]

        # Use Gemini to pick the best one and rephrase it into a YouTube topic
        system_prompt = """
        You are an expert YouTube producer. I will give you a list of trending news headlines.
        Pick the ONE headline that has the highest potential for a viral explainer or countdown video.
        Rephrase it into a compelling, broad YouTube topic (not a clickbait title, but a topic description).
        Each title must be under 70 characters.
        Reply ONLY with the topic string, nothing else.
        """
        
        user_prompt = "Headlines:\n" + "\n".join(f"- {h}" for h in headlines)
        
        try:
            topic = call_gemini(system_prompt, user_prompt).strip().strip('"').strip("'")
            if len(topic) > 70:
                shorten_prompt = f"Shorten this YouTube title to under 70 characters while keeping the curiosity gap and specificity. Return only the shortened title, nothing else.\nTitle: {topic}"
                topic = call_gemini("You are an expert YouTube producer.", shorten_prompt).strip().strip('"').strip("'")
            return topic
        except Exception as e:
            print(f"LLM topic generation failed: {e}")
            return random.choice(headlines)

if __name__ == "__main__":
    generator = TopicGenerator()
    print("Generated Topic:", generator.get_trending_topic())
