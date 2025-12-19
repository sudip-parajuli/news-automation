import os
import asyncio
from telethon import TelegramClient
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

class TelegramFetcher:
    def __init__(self, api_id: str, api_hash: str, phone: str = None):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.client = TelegramClient('news_session', api_id, api_hash)

    async def fetch_channel_news(self, channel_username: str, limit: int = 10) -> List[Dict]:
        """
        Fetches recent messages from a public Telegram channel.
        Note: This requires valid API credentials.
        """
        news_items = []
        try:
            await self.client.start(phone=self.phone)
            async for message in self.client.iter_messages(channel_username, limit=limit):
                if message.text:
                    news_items.append({
                        "headline": message.text.split('\n')[0][:100], # First line as headline
                        "content": message.text,
                        "source": f"Telegram: {channel_username}",
                        "published_time": str(message.date),
                        "url": f"https://t.me/{channel_username}/{message.id}"
                    })
        except Exception as e:
            print(f"Error fetching from Telegram channel {channel_username}: {e}")
        finally:
            await self.client.disconnect()
        return news_items

if __name__ == "__main__":
    # This requires API_ID and API_HASH to be set in .env
    API_ID = os.getenv("TELEGRAM_API_ID")
    API_HASH = os.getenv("TELEGRAM_API_HASH")
    
    if API_ID and API_HASH:
        fetcher = TelegramFetcher(API_ID, API_HASH)
        # Example channel: "durov" (just for testing structure)
        # loop = asyncio.get_event_loop()
        # news = loop.run_until_complete(fetcher.fetch_channel_news("durov"))
        # print(f"Fetched {len(news)} items.")
    else:
        print("Telegram API credentials not found in environment variables.")
