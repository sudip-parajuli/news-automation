import os
import re
import textwrap
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv
from scripts.llm_utils import call_gemini
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

load_dotenv()

# ─── Paths ────────────────────────────────────────────────────────────────────
ASSETS_DIR = Path(__file__).parent.parent / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
OSWALD_PATH = FONTS_DIR / "Oswald-Bold.ttf"
INTER_PATH = FONTS_DIR / "Inter-Bold.ttf"

FONT_URLS = {
    "oswald": "https://cdn.jsdelivr.net/fontsource/fonts/oswald@latest/latin-700-normal.ttf",
    "inter": "https://cdn.jsdelivr.net/fontsource/fonts/inter@latest/latin-700-normal.ttf",
}

# YouTube thumbnail dimensions
LONGFORM_SIZE = (1280, 720)
SHORTS_SIZE = (1080, 1920)

# Brand colours
ACCENT = (232, 69, 69)       # #E84545
BG_TOP = (26, 26, 46)        # #1a1a2e
BG_BOTTOM = (22, 33, 62)     # #16213e


# ─── Retry decorator (same pattern as Phase 3/4) ─────────────────────────────
def _llm_retry():
    return retry(
        wait=wait_exponential(min=2, max=30),
        stop=stop_after_attempt(4),
        reraise=True,
        retry=retry_if_exception_type((Exception,)),
    )


# ─── Font download ─────────────────────────────────────────────────────────────
def download_fonts() -> dict:
    """
    Downloads Oswald-Bold.ttf and Inter-Bold.ttf to assets/fonts/.
    Idempotent — skips files that already exist.
    Returns {"oswald": Path, "inter": Path}.
    """
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    paths = {"oswald": OSWALD_PATH, "inter": INTER_PATH}

    for key, dest in [("oswald", OSWALD_PATH), ("inter", INTER_PATH)]:
        if dest.exists():
            print(f"Font already present: {dest.name}")
            continue
        url = FONT_URLS[key]
        print(f"Downloading {dest.name} from GitHub...")
        response = httpx.get(url, follow_redirects=True, timeout=30.0)
        response.raise_for_status()
        dest.write_bytes(response.content)
        print(f"Saved {dest.name} ({len(response.content) // 1024} KB)")

    return paths


def _get_fonts(headline_size: int = 72, sub_size: int = 28, tag_size: int = 24):
    """Load TTF fonts, falling back gracefully with a warning."""
    try:
        headline = ImageFont.truetype(str(OSWALD_PATH), headline_size)
        sub = ImageFont.truetype(str(INTER_PATH), sub_size)
        tag = ImageFont.truetype(str(INTER_PATH), tag_size)
        return headline, sub, tag, True  # True = TTF loaded
    except (IOError, OSError):
        print("WARNING: TTF fonts not found — using Pillow bitmap default. Run download_fonts() first.")
        default = ImageFont.load_default()
        return default, default, default, False


# ─── Gradient helpers ──────────────────────────────────────────────────────────
def _draw_solid_gradient_bg(size: tuple[int, int]) -> Image.Image:
    """Draw a solid vertical gradient from BG_TOP to BG_BOTTOM."""
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)
    w, h = size
    for y in range(h):
        t = y / h
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return img


def _apply_overlay_gradient(img: Image.Image) -> Image.Image:
    """Apply a semi-transparent black ramp over the bottom 60% of the image."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    gradient_start_y = int(img.height * 0.4)
    for y in range(gradient_start_y, img.height):
        alpha = int(180 * (y - gradient_start_y) / (img.height - gradient_start_y))
        draw.line([(0, y), (img.width, y)], fill=(0, 0, 0, alpha))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


# ─── Thumbnail generators ──────────────────────────────────────────────────────
def generate_longform_thumbnail(
    title: str,
    topic: str,
    keywords: list[str],
    output_path: str,
    background_image_path: str | None = None,
) -> str:
    """
    Generate a 1280×720 YouTube thumbnail PNG.
    Uses background_image_path if provided, otherwise draws a dark gradient bg.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # 1. Background
    if background_image_path and os.path.exists(background_image_path):
        img = Image.open(background_image_path).convert("RGB")
        img = img.resize(LONGFORM_SIZE, Image.LANCZOS)
    else:
        img = _draw_solid_gradient_bg(LONGFORM_SIZE)

    # 2. Bottom overlay gradient
    img = _apply_overlay_gradient(img)

    draw = ImageDraw.Draw(img)
    w, h = LONGFORM_SIZE
    headline_font, sub_font, tag_font, ttf_loaded = _get_fonts(72, 28, 26)
    PADDING = 60

    # 3. Topic tag (e.g. "OIL PRICES")
    tag_text = topic.upper()[:30]
    tag_y = h - 180
    draw.text((PADDING, tag_y), tag_text, font=tag_font, fill=ACCENT)

    # 4. Accent bar
    bar_y = h - 155
    draw.rectangle([(PADDING, bar_y), (w - PADDING, bar_y + 5)], fill=ACCENT)

    # 5. Title text — word-wrap to max width
    max_text_width = w - (PADDING * 2)
    # Estimate chars per line for the font size; wrap conservatively
    wrapped = textwrap.fill(title, width=32)
    title_y = h - 140
    draw.text((PADDING, title_y), wrapped, font=headline_font, fill=(255, 255, 255),
              spacing=8)

    img.save(output_path, "PNG")
    print(f"Saved thumbnail: {output_path} | TTF font: {ttf_loaded}")
    return output_path


def generate_shorts_thumbnail(
    headline: str,
    output_path: str,
    background_image_path: str | None = None,
) -> str:
    """Generate a 1080×1920 YouTube Shorts thumbnail PNG."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    if background_image_path and os.path.exists(background_image_path):
        img = Image.open(background_image_path).convert("RGB")
        img = img.resize(SHORTS_SIZE, Image.LANCZOS)
    else:
        img = _draw_solid_gradient_bg(SHORTS_SIZE)

    img = _apply_overlay_gradient(img)
    draw = ImageDraw.Draw(img)
    w, h = SHORTS_SIZE
    headline_font, _, tag_font, ttf_loaded = _get_fonts(96, 36, 32)
    PADDING = 80

    tag_y = h - 320
    draw.text((PADDING, tag_y), "WATCH NOW", font=tag_font, fill=ACCENT)
    draw.rectangle([(PADDING, h - 285), (w - PADDING, h - 280)], fill=ACCENT)

    wrapped = textwrap.fill(headline, width=22)
    draw.text((PADDING, h - 270), wrapped, font=headline_font, fill=(255, 255, 255), spacing=10)

    img.save(output_path, "PNG")
    print(f"Saved Shorts thumbnail: {output_path} | TTF font: {ttf_loaded}")
    return output_path


# ─── LLM Title Selection ───────────────────────────────────────────────────────
@_llm_retry()
def _call_llm(system_prompt: str, user_prompt: str) -> str:
    return call_gemini(system_prompt, user_prompt)


def select_best_thumbnail(
    title_a: str,
    title_b: str,
    topic: str,
) -> tuple[str, str]:
    """
    Use LLM to pick the higher-CTR title between two variants.
    Returns (winning_title, reasoning_sentence).
    """
    system_prompt = (
        "You are a YouTube CTR optimization expert. "
        "Evaluate YouTube thumbnail titles for click-through potential. "
        "Reply with ONLY the letter A or B on the first line, "
        "then a single sentence of reasoning on the next line. No other text."
    )
    user_prompt = (
        f"Given these two YouTube thumbnail title variants for a video about '{topic}', "
        f"choose which title has higher predicted CTR based on curiosity gap, specificity, "
        f"and emotional impact.\n\n"
        f"Variant A: {title_a}\n"
        f"Variant B: {title_b}"
    )

    response = _call_llm(system_prompt, user_prompt)
    lines = [l.strip() for l in response.strip().splitlines() if l.strip()]

    choice = ""
    reasoning = ""
    for line in lines:
        if not choice and re.match(r'^[AaBb][\.\):]?$', line):
            choice = line[0].upper()
        elif len(line) > 5:
            reasoning = line
            break

    # Fallback if parsing fails
    if choice not in ("A", "B"):
        choice = "A" if "a" in response.lower()[:10] else "B"
    if not reasoning:
        reasoning = response

    winning_title = title_a if choice == "A" else title_b
    return winning_title, reasoning
