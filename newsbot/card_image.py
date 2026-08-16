import os

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1080, 1080

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
TEMPLATE_PATH = os.path.join(ASSETS_DIR, "card_template.jpg")

TITLE_COLOR = (25, 25, 25)
SUBTITLE_COLOR = (55, 55, 55)

# The template has three fixed zones: a blank strip at the top for the
# headline, the branded Kathmandu-skyline watermark in the middle (left
# untouched), and a blank strip below it -- above the social-icons footer --
# for the longer subtitle text.
TITLE_TOP, TITLE_BOTTOM = 40, 300
SUBTITLE_TOP, SUBTITLE_BOTTOM = 650, 1010
TEXT_MAX_WIDTH = WIDTH - 140

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


def _fit_block(draw, text, max_width, max_height, bold, start_size, min_size, line_gap_ratio=1.3):
    """Shrink the font size until the wrapped text block fits max_height."""
    candidates = FONT_BOLD_CANDIDATES if bold else FONT_REGULAR_CANDIDATES
    size = start_size
    while size >= min_size:
        font = _load_font(candidates, size)
        lines = _wrap_text(draw, text, font, max_width)
        line_height = int(size * line_gap_ratio)
        block_height = line_height * len(lines)
        if block_height <= max_height:
            return font, lines, line_height
        size -= 4
    font = _load_font(candidates, min_size)
    lines = _wrap_text(draw, text, font, max_width)
    return font, lines, int(min_size * line_gap_ratio)


def _draw_centered_block(draw, lines, font, line_height, zone_top, zone_bottom, fill):
    block_height = line_height * len(lines)
    y = zone_top + max(0, (zone_bottom - zone_top - block_height) // 2)
    for line in lines:
        w = draw.textlength(line, font=font)
        draw.text(((WIDTH - w) / 2, y), line, font=font, fill=fill)
        y += line_height


def generate_card(headline_ne, subtitle_ne, output_path):
    base = Image.open(TEMPLATE_PATH).convert("RGB")
    if base.size != (WIDTH, HEIGHT):
        base = base.resize((WIDTH, HEIGHT))
    img = base.copy()
    draw = ImageDraw.Draw(img)

    title_font, title_lines, title_line_h = _fit_block(
        draw, headline_ne, TEXT_MAX_WIDTH, TITLE_BOTTOM - TITLE_TOP, bold=True,
        start_size=76, min_size=48,
    )
    _draw_centered_block(draw, title_lines, title_font, title_line_h, TITLE_TOP, TITLE_BOTTOM, TITLE_COLOR)

    subtitle_font, subtitle_lines, subtitle_line_h = _fit_block(
        draw, subtitle_ne, TEXT_MAX_WIDTH, SUBTITLE_BOTTOM - SUBTITLE_TOP, bold=False,
        start_size=40, min_size=26,
    )
    _draw_centered_block(draw, subtitle_lines, subtitle_font, subtitle_line_h, SUBTITLE_TOP, SUBTITLE_BOTTOM, SUBTITLE_COLOR)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "JPEG", quality=92)
    return output_path
