import os

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1080, 1350

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
TEMPLATE_PATH = os.path.join(ASSETS_DIR, "card_template.jpg")

TITLE_COLOR = (20, 20, 20)
SUBTITLE_COLOR = (70, 70, 70)

# The template's blank area sits roughly in the top 40% of the image, above
# the Kathmandu-skyline watermark and the footer bar with the social icons.
TEXT_TOP = 130
TEXT_BOTTOM = 560
TEXT_MAX_WIDTH = WIDTH - 140

# Roman (Latin) script only -- DejaVu Sans has full coverage, so there's no
# more "missing glyph" tofu-box problem like there was with Devanagari.
FONT_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
FONT_REGULAR_CANDIDATES = [
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


def _fit_block(draw, text, max_width, max_height, bold, start_size, min_size, line_gap_ratio=1.25):
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


def generate_card(title_roman, subtitle_roman, output_path):
    base = Image.open(TEMPLATE_PATH).convert("RGB")
    if base.size != (WIDTH, HEIGHT):
        base = base.resize((WIDTH, HEIGHT))
    img = base.copy()
    draw = ImageDraw.Draw(img)

    available_height = TEXT_BOTTOM - TEXT_TOP
    title_budget = int(available_height * 0.62)
    subtitle_budget = available_height - title_budget - 30

    title_font, title_lines, title_line_h = _fit_block(
        draw, title_roman.upper(), TEXT_MAX_WIDTH, title_budget, bold=True,
        start_size=84, min_size=44,
    )
    subtitle_font, subtitle_lines, subtitle_line_h = _fit_block(
        draw, subtitle_roman, TEXT_MAX_WIDTH, subtitle_budget, bold=False,
        start_size=42, min_size=26,
    )

    title_block_h = title_line_h * len(title_lines)
    subtitle_block_h = subtitle_line_h * len(subtitle_lines)
    total_h = title_block_h + 30 + subtitle_block_h
    y = TEXT_TOP + max(0, (available_height - total_h) // 2)

    for line in title_lines:
        w = draw.textlength(line, font=title_font)
        draw.text(((WIDTH - w) / 2, y), line, font=title_font, fill=TITLE_COLOR)
        y += title_line_h

    y += 30

    for line in subtitle_lines:
        w = draw.textlength(line, font=subtitle_font)
        draw.text(((WIDTH - w) / 2, y), line, font=subtitle_font, fill=SUBTITLE_COLOR)
        y += subtitle_line_h

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "JPEG", quality=92)
    return output_path
