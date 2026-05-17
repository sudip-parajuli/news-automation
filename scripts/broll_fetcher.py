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
    def _extract_all_keywords(self, sections: dict) -> dict:
        system_prompt = """
        Given these 7 script sections, generate one 2-4 word video search query for each.
        Each query must be concrete and visual (suitable for stock footage search).
        Return ONLY a JSON object with section names as keys:
        {
          "hook": "query here",
          "context": "query here", 
          "conflict": "query here",
          "evidence": "query here",
          "twist": "query here",
          "resolution": "query here",
          "cta": "query here"
        }
        """
        
        user_prompt = "Sections:\n"
        for name, text in sections.items():
            user_prompt += f"{name}: {text}\n"
            
        response = call_gemini(system_prompt, user_prompt)
        
        # Clean up possible markdown json blocks
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
            
        try:
            return json.loads(response.strip())
        except json.JSONDecodeError as e:
            print(f"Failed to parse batched keywords JSON: {response}")
            raise ValueError(f"Failed to parse batched keywords JSON: {e}")

    def fetch_broll(self, query: str) -> dict:
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
        try:
            batched_queries = self._extract_all_keywords(sections)
        except Exception as e:
            print(f"Failed to extract batched keywords: {e}")
            batched_queries = {}
            
        for section_name, section_text in sections.items():
            results[section_name] = []
            query = batched_queries.get(section_name)
            if not query:
                # Fallback to a basic extract if missing
                query = "news footage"
                
            try:
                broll = self.fetch_broll(query)
                results[section_name].append(broll)
            except Exception as e:
                print(f"Failed to fetch broll for section {section_name} with query {query}: {e}")
                
        return results
