import os
import json
import asyncio
from datetime import datetime
from dotenv import load_dotenv

from fetchers.rss_fetcher import RSSFetcher
from processors.classifier import NewsClassifier
from processors.rewrite_breaking import ScriptRewriter
from media.tts_english import TTSEngine
from media.video_long import VideoLongGenerator
from uploader.youtube_uploader import YouTubeUploader

load_dotenv()

FEEDS = [
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.aljazeera.com/rss/world"
]
DAILY_BUCKET = "storage/daily_news_bucket.json"

async def main():
    if not os.path.exists("storage"):
        os.makedirs("storage")

    # 1. Fetch and Collect
    fetcher = RSSFetcher(FEEDS)
    news_items = fetcher.fetch_all()
    
    # 2. Daily summary logic
    # In a full system, we might store items throughout the day.
    # For this MVP, we'll summarize the current top news.
    
    classifier = NewsClassifier()
    normal_news = [item for item in news_items if classifier.classify(item) == "NORMAL"][:10]
    
    if not normal_news:
        print("No news to summarize.")
        return

    rewriter = ScriptRewriter(os.getenv("GEMINI_API_KEY"))
    script = rewriter.summarize_for_daily(normal_news)
    
    # 3. Generate Media
    audio_path = "storage/daily_summary.mp3"
    await TTSEngine.generate_audio(script, audio_path)
    
    vgen = VideoLongGenerator()
    # Create sections for the slideshow (simple version)
    sections = []
    lines = script.split('.')
    for line in lines:
        if len(line.strip()) > 10:
            sections.append({'text': line.strip(), 'image_path': None})
    
    video_path = "storage/daily_summary.mp4"
    if sections:
        vgen.create_daily_summary(sections, audio_path, video_path)
    
        # 4. Upload
        uploader = YouTubeUploader() if os.path.exists("client_secrets.json") else None
        if uploader:
            uploader.upload_video(
                video_path,
                f"World News Today | {datetime.now().strftime('%Y-%m-%d')} Global Headlines",
                f"Global news summary for today.\n\nSummary:\n{script}",
                ["WorldNews", "DailyNews", "Summary"],
                category_id="25"
            )

if __name__ == "__main__":
    asyncio.run(main())
