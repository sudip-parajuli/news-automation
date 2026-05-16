import os
import hashlib
import json
import httpx
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from scripts.llm_utils import call_gemini

KEN_BURNS_FILTER = "zoompan=z='min(zoom+0.0015,1.5)':d={duration_frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080"

def llm_retry_decorator():
    return retry(
        wait=wait_exponential(min=2, max=30),
        stop=stop_after_attempt(4),
        reraise=True,
        retry=retry_if_exception_type((Exception,))
    )

class BRollFetcher:
    def __init__(self, cache_dir: str = "output/broll_cache"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        
        self.pexels_api_key = os.getenv("PEXELS_API_KEY")
        if not self.pexels_api_key:
            print("WARNING: PEXELS_API_KEY not found. Video fetching may fail.")

    @llm_retry_decorator()
    def _extract_keywords(self, sentence: str) -> str:
        system_prompt = """
        You are an expert at extracting highly searchable stock video keywords from narrative sentences.
        Extract a 2-4 word query that captures the core visual subject.
        Output ONLY the query string, nothing else. No quotes, no explanation.
        Example: "OPEC ministers met in Vienna to discuss production cuts amid falling crude prices" -> "OPEC oil ministers"
        """
        return call_gemini(system_prompt, sentence).strip()

    def fetch_broll(self, sentence: str) -> dict:
        query = self._extract_keywords(sentence)
        query_hash = hashlib.md5(query.encode('utf-8')).hexdigest()
        
        cached_info_path = os.path.join(self.cache_dir, f"{query_hash}.json")
        if os.path.exists(cached_info_path):
            with open(cached_info_path, 'r') as f:
                return json.load(f)

        if not self.pexels_api_key:
            raise ValueError("PEXELS_API_KEY is required to fetch B-roll")

        headers = {"Authorization": self.pexels_api_key}
        url = f"https://api.pexels.com/videos/search?query={query}&orientation=landscape&size=medium&per_page=5"
        
        response = httpx.get(url, headers=headers, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        
        for video in data.get("videos", []):
            duration = video.get("duration", 0)
            if 4 <= duration <= 15:
                for video_file in video.get("video_files", []):
                    if video_file.get("quality") == "sd":
                        link = video_file.get("link")
                        if link:
                            base_path = os.path.join(self.cache_dir, query_hash)
                            file_path = self._download_file(link, base_path)
                            
                            result = {
                                "query": query,
                                "file_path": file_path,
                                "type": "video",
                                "duration": duration,
                                "filter": None
                            }
                            
                            with open(cached_info_path, 'w') as f:
                                json.dump(result, f)
                            return result

        # Fallback to image if no valid video is found
        image_url = f"https://api.pexels.com/v1/search?query={query}&orientation=landscape&size=large&per_page=1"
        response = httpx.get(image_url, headers=headers, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        
        if data.get("photos"):
            photo = data["photos"][0]
            link = photo.get("src", {}).get("large")
            if link:
                base_path = os.path.join(self.cache_dir, query_hash)
                file_path = self._download_file(link, base_path)
                
                fps = 30
                duration = 5
                duration_frames = fps * duration
                kb_filter = KEN_BURNS_FILTER.replace("{duration_frames}", str(duration_frames))
                
                result = {
                    "query": query,
                    "file_path": file_path,
                    "type": "still_image",
                    "duration": duration,
                    "filter": kb_filter
                }
                
                with open(cached_info_path, 'w') as f:
                    json.dump(result, f)
                return result

        raise ValueError(f"Could not find any suitable video or image for query: {query}")

    def _download_file(self, url: str, base_path: str) -> str:
        with httpx.stream("GET", url) as response:
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "")
            
            if "video/mp4" in content_type:
                ext = "mp4"
            elif "video/quicktime" in content_type:
                ext = "mov"
            elif "image/jpeg" in content_type:
                ext = "jpg"
            elif "image/png" in content_type:
                ext = "png"
            else:
                ext = url.split("?")[0].split(".")[-1]
                if len(ext) > 4 or not ext:
                    ext = "bin"
            
            final_path = f"{base_path}.{ext}"
            
            with open(final_path, "wb") as f:
                for chunk in response.iter_bytes():
                    f.write(chunk)
            return final_path

    def fetch_broll_for_script(self, sections: dict) -> dict:
        results = {}
        for section_name, section_text in sections.items():
            results[section_name] = []
            try:
                broll = self.fetch_broll(section_text)
                results[section_name].append(broll)
            except Exception as e:
                print(f"Failed to fetch broll for section {section_name}: {e}")
                
        return results
