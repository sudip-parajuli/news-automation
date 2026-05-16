import os
import sys
import glob
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.thumbnail_generator import (
    download_fonts,
    generate_longform_thumbnail,
    select_best_thumbnail,
    OSWALD_PATH,
)


def main():
    print("=== Phase 9 Thumbnail Smoke Test ===\n")

    # 1. Find the latest script JSON
    matches = sorted(glob.glob("output/scripts/why_oil_prices_are_spiking_globally_*.json"))
    if not matches:
        matches = sorted(glob.glob("output/scripts/*.json"))
    if not matches:
        print("ERROR: No script JSON found. Run smoke_test.py first.")
        sys.exit(1)

    script_path = matches[-1]
    print(f"Using script: {script_path}")

    with open(script_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    metadata = data.get("metadata", {})
    title_options = metadata.get("title_options", [])
    thumbnail_keywords = metadata.get("thumbnail_keywords", [])
    topic = data.get("topic", "global oil prices")

    if len(title_options) < 2:
        print(f"ERROR: Need at least 2 title options, got: {title_options}")
        sys.exit(1)

    title_a = title_options[0]
    title_b = title_options[1]
    print(f"Topic: {topic}")
    print(f"Title A: {title_a}")
    print(f"Title B: {title_b}")
    print(f"Keywords: {thumbnail_keywords}\n")

    # 2. Download fonts (idempotent)
    print("Ensuring fonts are available...")
    download_fonts()
    ttf_loaded = OSWALD_PATH.exists()
    print(f"Oswald-Bold.ttf present: {ttf_loaded}\n")

    # 3. Generate thumbnails
    os.makedirs("output/thumbnails", exist_ok=True)

    path_a = "output/thumbnails/thumbnail_a.png"
    path_b = "output/thumbnails/thumbnail_b.png"

    print("Generating Variant A...")
    generate_longform_thumbnail(title_a, topic, thumbnail_keywords, path_a)

    print("Generating Variant B...")
    generate_longform_thumbnail(title_b, topic, thumbnail_keywords, path_b)

    # 4. Confirm files exist
    a_exists = os.path.exists(path_a)
    b_exists = os.path.exists(path_b)
    print(f"\nthumbnail_a.png exists: {a_exists} ({os.path.getsize(path_a) // 1024}KB)")
    print(f"thumbnail_b.png exists: {b_exists} ({os.path.getsize(path_b) // 1024}KB)")

    # 5. Select best thumbnail
    print(f"\nCalling select_best_thumbnail()...")
    winning_title, reasoning = select_best_thumbnail(title_a, title_b, topic)

    print(f"\n{'='*60}")
    print(f"WINNING TITLE: {winning_title}")
    print(f"REASONING:     {reasoning}")
    print(f"{'='*60}")

    # 6. Final checks
    font_check = "PASS (TTF font loaded)" if ttf_loaded else "FAIL (bitmap fallback used)"
    all_pass = a_exists and b_exists and bool(winning_title)

    print(f"\nFont check: {font_check}")
    print(f"Both PNGs exist: {'PASS' if a_exists and b_exists else 'FAIL'}")
    print(f"\n--- SMOKE TEST {'PASSED' if all_pass else 'FAILED'} ---")

    if not all_pass:
        sys.exit(1)


if __name__ == "__main__":
    main()
