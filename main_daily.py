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

async def main():
    if not os.path.exists("storage"):
        os.makedirs("storage")

    fetcher = RSSFetcher(FEEDS)
    news_items = fetcher.fetch_all()
    
    classifier = NewsClassifier()
    normal_news = [item for item in news_items if classifier.classify(item) == "NORMAL"][:10]
    
    if not normal_news:
        print("No news to summarize.")
        return

    from media.image_fetcher import ImageFetcher
    img_fetcher = ImageFetcher()
    rewriter = ScriptRewriter(os.getenv("GEMINI_API_KEY"))
    script = rewriter.summarize_for_daily(normal_news)
    
    audio_path = "storage/daily_summary.mp3"
    _, word_offsets = await TTSEngine.generate_audio(script, audio_path)
    
    vgen = VideoLongGenerator()
    sections = []
    # Batching Optimization: Group sentences to reduce API calls (Target ~200-300 chars per section)
    raw_sentences = [s.strip() + "." for s in script.split('.') if len(s.strip()) > 10]
    chunked_sections = []
    temp_images = []
    current_chunk = ""
    
    for sent in raw_sentences:
        if len(current_chunk) + len(sent) < 280:
            current_chunk += " " + sent
        else:
            chunked_sections.append(current_chunk.strip())
            current_chunk = sent
    if current_chunk:
        chunked_sections.append(current_chunk.strip())
            
    print(f"Optimization: Reduced {len(raw_sentences)} sentences to {len(chunked_sections)} image sections.")

    print("Fetching images for summary sections...")
    for i, text in enumerate(chunked_sections):
        if len(text) > 10:
            # Generate AI keywords for better image context
            try:
                keywords = rewriter.generate_image_keywords(text)
            except Exception as e:
                print(f"Keyword gen failed: {e}")
                keywords = ""
            
            if not keywords or len(keywords) < 3 or keywords.lower() == 'none':
                print(f"Skipping image for section {i} (no valid keywords)")
                sections.append({'text': text, 'image_path': None})
                continue

            img_name = f"summary_img_{i}.jpg"
            print(f"Section {i} keywords: {keywords}")
            img_path = img_fetcher.fetch_image(keywords, img_name)
            sections.append({'text': text, 'image_path': img_path})
            if img_path: temp_images.append(img_path)
            
            # Rate limit politeness
            import time
            time.sleep(1.5)
    
    video_path = "storage/daily_summary.mp4"
    if sections:
        vgen.create_daily_summary(sections, audio_path, video_path, word_offsets=word_offsets)
    
        uploader = YouTubeUploader() if (os.path.exists("client_secrets.json") or os.path.exists("client_secret.json") or os.getenv("YOUTUBE_TOKEN_BASE64")) else None
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
