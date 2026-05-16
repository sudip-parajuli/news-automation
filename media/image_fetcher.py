import os
import hashlib
import re
import httpx
from pathlib import Path
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

# ─── Paths ────────────────────────────────────────────────────────────────────
CACHE_DIR = "output/image_cache"
FALLBACK_DIR = "output"
ASSETS_DIR = Path(__file__).parent.parent / "assets"
OSWALD_PATH = ASSETS_DIR / "fonts" / "Oswald-Bold.ttf"

# Wikimedia: reject these URL patterns
WIKIMEDIA_BAD_PATTERNS = [".svg", "diagram", "map", "chart", "flag", "logo", "icon"]

# ─── Retry decorator ─────────────────────────────────────────────────────────
def _retry():
    return retry(
        wait=wait_exponential(min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
        retry=retry_if_exception_type((Exception,)),
    )


def _query_hash(query: str) -> str:
    return hashlib.md5(query.encode("utf-8")).hexdigest()


def _is_valid_image_url(url: str) -> bool:
    """Accept only .jpg and .png URLs."""
    lower = url.lower().split("?")[0]
    return lower.endswith(".jpg") or lower.endswith(".jpeg") or lower.endswith(".png")


def _save_cache(data: bytes, query_hash: str, ext: str = "jpg") -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{query_hash}.{ext}")
    with open(path, "wb") as f:
        f.write(data)
    return path


# ─── Source 1: Pexels ────────────────────────────────────────────────────────
@_retry()
def _fetch_from_pexels(query: str, query_hash: str) -> str | None:
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        return None

    url = f"https://api.pexels.com/v1/search?query={query}&per_page=5&orientation=landscape"
    headers = {"Authorization": api_key}
    resp = httpx.get(url, headers=headers, timeout=15.0)
    resp.raise_for_status()
    data = resp.json()

    for photo in data.get("photos", []):
        # Filter out generic Pexels stock
        if photo.get("photographer", "") == "Pexels":
            continue
        img_url = photo.get("src", {}).get("large2x") or photo.get("src", {}).get("large")
        if not img_url:
            continue
        img_resp = httpx.get(img_url, timeout=20.0, follow_redirects=True)
        if img_resp.status_code == 200 and len(img_resp.content) > 30000:
            return _save_cache(img_resp.content, query_hash)

    return None


# ─── Source 2: Pixabay ───────────────────────────────────────────────────────
@_retry()
def _fetch_from_pixabay(query: str, query_hash: str) -> str | None:
    api_key = os.getenv("PIXABAY_API_KEY")
    if not api_key:
        return None

    url = (
        f"https://pixabay.com/api/?key={api_key}&q={query}"
        f"&image_type=photo&per_page=5&safesearch=true&editors_choice=false"
    )
    resp = httpx.get(url, timeout=15.0)
    resp.raise_for_status()
    data = resp.json()

    for hit in data.get("hits", []):
        img_url = hit.get("largeImageURL")
        if not img_url or not _is_valid_image_url(img_url):
            continue
        img_resp = httpx.get(img_url, timeout=20.0, follow_redirects=True)
        if img_resp.status_code == 200 and len(img_resp.content) > 30000:
            return _save_cache(img_resp.content, query_hash)

    return None


# ─── Source 3: Wikimedia Commons ─────────────────────────────────────────────
@_retry()
def _fetch_from_wikimedia(query: str, query_hash: str) -> str | None:
    slug = re.sub(r"\s+", "_", query.strip())

    # 3a: Wikipedia page thumbnail
    try:
        summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}"
        resp = httpx.get(summary_url, timeout=10.0, follow_redirects=True)
        if resp.status_code == 200:
            thumb = resp.json().get("thumbnail", {}).get("source", "")
            if thumb and _is_valid_image_url(thumb):
                bad = any(p in thumb.lower() for p in WIKIMEDIA_BAD_PATTERNS)
                if not bad:
                    img_resp = httpx.get(thumb, timeout=20.0, follow_redirects=True)
                    if img_resp.status_code == 200 and len(img_resp.content) > 20000:
                        return _save_cache(img_resp.content, query_hash)
    except Exception:
        pass

    # 3b: Wikimedia Commons image search
    commons_url = (
        "https://commons.wikimedia.org/w/api.php"
        f"?action=query&generator=search&gsrsearch={query}&gsrnamespace=6"
        "&prop=imageinfo&iiprop=url&format=json&gsrlimit=10"
    )
    resp = httpx.get(commons_url, timeout=10.0)
    if resp.status_code != 200:
        return None

    pages = resp.json().get("query", {}).get("pages", {})
    for page in pages.values():
        for info in page.get("imageinfo", []):
            img_url = info.get("url", "")
            if not img_url:
                continue
            lower_url = img_url.lower()
            bad = any(p in lower_url for p in WIKIMEDIA_BAD_PATTERNS)
            if bad:
                continue
            if not _is_valid_image_url(img_url):
                continue
            img_resp = httpx.get(img_url, timeout=20.0, follow_redirects=True)
            if img_resp.status_code == 200 and len(img_resp.content) > 20000:
                return _save_cache(img_resp.content, query_hash)

    return None


# ─── Source 4: Pillow Gradient Fallback ──────────────────────────────────────
def _generate_fallback(query: str, query_hash: str) -> str:
    from PIL import Image, ImageDraw
    import textwrap

    os.makedirs(FALLBACK_DIR, exist_ok=True)
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    # Dark gradient: #1a1a2e → #16213e
    TOP = (26, 26, 46)
    BOT = (22, 33, 62)
    for y in range(H):
        t = y / H
        r = int(TOP[0] + (BOT[0] - TOP[0]) * t)
        g = int(TOP[1] + (BOT[1] - TOP[1]) * t)
        b = int(TOP[2] + (BOT[2] - TOP[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Overlay headline text — silently skip if font missing
    try:
        from PIL import ImageFont
        font = ImageFont.truetype(str(OSWALD_PATH), 72)
        wrapped = textwrap.fill(query, width=20)
        # Measure bounding box
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=10)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (W - text_w) // 2
        y = (H - text_h) // 2
        # Black stroke (3px offset in each direction)
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                if dx != 0 or dy != 0:
                    draw.multiline_text((x + dx, y + dy), wrapped, font=font,
                                        fill=(0, 0, 0), spacing=10, align="center")
        # White fill
        draw.multiline_text((x, y), wrapped, font=font, fill=(255, 255, 255),
                             spacing=10, align="center")
    except Exception:
        pass  # Font missing — gradient alone is fine

    path = os.path.join(FALLBACK_DIR, f"fallback_bg_{query_hash}.jpg")
    img.save(path, "JPEG", quality=85)
    return path


# ─── Public API ──────────────────────────────────────────────────────────────
class ImageFetcher:
    """Multi-source image fetcher: Pexels → Pixabay → Wikimedia → Pillow fallback."""

    def __init__(self, download_dir: str = CACHE_DIR):
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)

    def fetch_image(self, query: str, filename: str = None) -> str | None:
        """
        Fetch an image for `query`. Returns local file path.
        `filename` is accepted for API compatibility but ignored (we use content hash).
        """
        q_hash = _query_hash(query)
        # Check cache first
        cached = os.path.join(CACHE_DIR, f"{q_hash}.jpg")
        if os.path.exists(cached):
            print(f"[ImageFetcher] Cache hit for: {query}")
            return cached

        # Source 1: Pexels
        try:
            path = _fetch_from_pexels(query, q_hash)
            if path:
                print(f"[ImageFetcher] Source: Pexels | {query}")
                return path
        except Exception as e:
            print(f"[ImageFetcher] Pexels failed: {e}")

        # Source 2: Pixabay
        try:
            path = _fetch_from_pixabay(query, q_hash)
            if path:
                print(f"[ImageFetcher] Source: Pixabay | {query}")
                return path
        except Exception as e:
            print(f"[ImageFetcher] Pixabay failed: {e}")

        # Source 3: Wikimedia Commons
        try:
            path = _fetch_from_wikimedia(query, q_hash)
            if path:
                print(f"[ImageFetcher] Source: Wikimedia | {query}")
                return path
        except Exception as e:
            print(f"[ImageFetcher] Wikimedia failed: {e}")

        # Source 4: Pillow fallback gradient
        print(f"[ImageFetcher] Source: Fallback (gradient) | {query}")
        return _generate_fallback(query, q_hash)

    def fetch_multi_images(self, queries: list, base_filename: str) -> list:
        """Fetch one image per query string. Returns list of local paths."""
        paths = []
        for i, q in enumerate(queries):
            path = self.fetch_image(q, f"{base_filename}_{i}.jpg")
            if path:
                paths.append(path)
        return paths


# ─── Module-level alias (used by smoke test and shorts pipeline) ──────────────
def fetch_image(keywords: list) -> str:
    """
    Convenience wrapper — accepts a list of keyword strings,
    joins them into a query, and returns a local image path.
    Always returns a path (fallback gradient at minimum).
    """
    query = " ".join(keywords) if isinstance(keywords, list) else str(keywords)
    fetcher = ImageFetcher()
    return fetcher.fetch_image(query)
