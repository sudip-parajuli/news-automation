import os

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1080, 1350
BG_COLOR = (17, 20, 28)
ACCENT_COLOR = (230, 57, 70)
TEXT_COLOR = (255, 255, 255)
MUTED_COLOR = (170, 176, 190)

# fonts-noto-core (installed by the workflow via apt) ships Devanagari-capable
# Noto Sans fonts at these paths on Ubuntu runners.
FONT_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
FONT_REGULAR_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _load_font(candidates, size):
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _wrap_text(draw, text, font, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]


def generate_card(headline_ne, source, category_label, output_path):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, WIDTH, 14], fill=ACCENT_COLOR)
    draw.rectangle([0, HEIGHT - 14, WIDTH, HEIGHT], fill=ACCENT_COLOR)

    brand_font = _load_font(FONT_BOLD_CANDIDATES, 40)
    draw.text((60, 60), "TRENDING TODAY", font=brand_font, fill=ACCENT_COLOR)

    tag_font = _load_font(FONT_BOLD_CANDIDATES, 30)
    draw.text((60, 128), category_label.upper(), font=tag_font, fill=MUTED_COLOR)

    headline_font = _load_font(FONT_BOLD_CANDIDATES, 62)
    max_text_width = WIDTH - 120
    lines = _wrap_text(draw, headline_ne, headline_font, max_text_width)
    line_height = 80
    total_height = line_height * len(lines)
    start_y = max(220, (HEIGHT - total_height) // 2)
    for i, line in enumerate(lines):
        draw.text((60, start_y + i * line_height), line, font=headline_font, fill=TEXT_COLOR)

    source_font = _load_font(FONT_REGULAR_CANDIDATES, 28)
    draw.text((60, HEIGHT - 90), f"Source: {source}", font=source_font, fill=MUTED_COLOR)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "JPEG", quality=90)
    return output_path
