import os
import json
import asyncio
from datetime import datetime
from dotenv import load_dotenv

from fetchers.rss_fetcher import RSSFetcher
from processors.classifier import NewsClassifier
from processors.rewrite_breaking import ScriptRewriter
from media.tts_english import TTSEngine
from media.video_shorts import VideoShortsGenerator
from uploader.youtube_uploader import YouTubeUploader

load_dotenv()

# Configuration
FEEDS = [
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.aljazeera.com/rss/world",
    "https://www.reutersagency.com/feed/?best-topics=world-news&post_type=best"
]
POSTED_FILE = "storage/posted_breaking.json"

async def main():
    if not os.path.exists("storage"):
        os.makedirs("storage")
    
    # Load posted news
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, 'r') as f:
            posted_hashes = json.load(f)
    else:
        posted_hashes = []

    # 1. Fetch
    fetcher = RSSFetcher(FEEDS)
    news_items = fetcher.fetch_all()

    # 2. Classify
    classifier = NewsClassifier()
    breaking_news = classifier.filter_breaking(news_items)

    # 3. Process new breaking news
    rewriter = ScriptRewriter(os.getenv("GEMINI_API_KEY"))
    vgen = VideoShortsGenerator()
    uploader = YouTubeUploader() if os.path.exists("client_secrets.json") else None

    for item in breaking_news:
        if item['hash'] not in posted_hashes:
            print(f"Processing breaking news: {item['headline']}")
            
            # Rewrite script
            script = rewriter.rewrite_for_shorts(item['headline'], item['content'])
            
            # Generate Audio
            audio_path = f"storage/temp_audio_{item['hash'][:8]}.mp3"
            await TTSEngine.generate_audio(script, audio_path)
            
            # Generate Video
            video_path = f"storage/breaking_{item['hash'][:8]}.mp4"
            vgen.create_shorts(script, audio_path, video_path)
            
            # Upload (if uploader initialized)
            if uploader:
                title = f"BREAKING: {item['headline'][:70]}"
                uploader.upload_video(
                    video_path, 
                    title, 
                    f"Breaking News Update. {script}\n\n#BreakingNews #WorldNews #Shorts", 
                    ["BreakingNews", "WorldNews", "Shorts"]
                )
            
            # Mark as posted
            posted_hashes.append(item['hash'])
            
            # Cleanup temp files
            if os.path.exists(audio_path): os.remove(audio_path)
            # We might want to keep the video or delete it
            
            # Only process one per run to avoid spamming/quota issues
            break 

    # Save updated hashes
    with open(POSTED_FILE, 'w') as f:
        json.dump(posted_hashes[-100:], f) # Keep last 100

if __name__ == "__main__":
    asyncio.run(main())
