"""
scripts/shorts_pipeline.py
===========================
Remotion-based Shorts pipeline orchestrator.

Replaces main_breaking.py when USE_REMOTION_SHORTS=true.
Reuses all existing fetching, classification, and TTS logic.
Only the render step is new (Remotion instead of MoviePy).

Entry point:
    python scripts/shorts_pipeline.py [--dry-run]
"""

import os
import re
import sys
import json
import shutil
import hashlib
import argparse
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ─── Add project root to path ────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

# ─── Imports from existing modules ───────────────────────────────────────────
from fetchers.rss_fetcher import RSSFetcher
from processors.classifier import NewsClassifier
from processors.rewrite_breaking import ScriptRewriter
from scripts.shorts_script_enhancer import enhance_shorts_script
from scripts.voiceover_generator import generate_voiceover, get_voiceover_duration
from scripts.broll_fetcher import BRollFetcher
from scripts.caption_utils import build_caption_chunks
from scripts.music_selector import select_music, apply_music_ducking
from uploader.youtube_uploader import YouTubeUploader

# ─── Constants ────────────────────────────────────────────────────────────────
MAX_SHORTS_PER_RUN = 3
POSTED_FILE = Path("storage/posted_breaking.json")

FEEDS = [
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.aljazeera.com/rss/world",
    "https://www.reutersagency.com/feed/?best-topics=world-news&post_type=best",
]


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _make_slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:50]


def _load_posted() -> list:
    POSTED_FILE.parent.mkdir(parents=True, exist_ok=True)
    if POSTED_FILE.exists():
        try:
            with open(POSTED_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save_posted(hashes: list):
    POSTED_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(POSTED_FILE, "w") as f:
        json.dump(hashes[-200:], f)


def _broll_for_headline(headline: str, n: int = 6) -> list:
    """
    Fetch `n` b-roll clips using BRollFetcher, seeded from the headline.
    Returns list of {"file": abs_path, "duration": float} for Remotion.
    """
    fetcher = BRollFetcher()
    clips = []

    # Generate n keyword variants from the headline words
    words = headline.split()
    queries = []
    step = max(1, len(words) // n)
    for i in range(n):
        start = (i * step) % len(words)
        phrase = " ".join(words[start : start + 3]) if len(words) >= 3 else headline
        queries.append(phrase)

    for q in queries:
        try:
            broll = fetcher.fetch_broll(q)
            fp = os.path.abspath(broll["file_path"])
            duration = min(float(broll.get("duration", 5.0)), 2.0)
            clips.append({"file": fp, "duration": duration})
        except Exception as e:
            print(f"[ShortsPipeline] B-roll fetch failed for '{q}': {e}")

    if not clips:
        # Absolute minimum — return a 2-second placeholder entry
        print("[ShortsPipeline] WARNING: No b-roll fetched. Using empty clip list.")

    return clips


def _assemble_remotion_data(
    headline: str,
    script_text: str,
    clips: list,
    vo_path: str,
    hook_text: str,
    loop_hook: str,
    music_path: str | None,
) -> dict:
    """Build the ShortFormVideoData payload for Remotion."""
    words = script_text.split()
    chunks = build_caption_chunks(words)
    caption_lines = [" ".join(chunk) for chunk in chunks]

    return {
        "headline": headline,
        "body_text": script_text,
        "clips": clips,
        "caption_lines": caption_lines,
        "voiceover_file": os.path.abspath(vo_path) if vo_path else "",
        "hook_text": hook_text,
        "loop_hook": loop_hook,
        "audio_track": os.path.abspath(music_path) if music_path and os.path.exists(music_path) else "",
    }


# ─── Remotion render (reused from previous shorts_pipeline.py) ────────────────
def _stream_render(composition: str, data_path: str, output_path: str):
    node_path = shutil.which("node")
    if not node_path:
        raise RuntimeError("node not found in PATH.")

    bundle_path_file = "output/pipeline_state/remotion_bundle_path.txt"
    needs_rebundle = True
    bundle_path = ""

    try:
        src_mtime = max(
            os.path.getmtime("remotion/src/index.tsx"),
            os.path.getmtime("remotion/src/compositions"),
        )
        if os.path.exists(bundle_path_file):
            bundle_cache_mtime = os.path.getmtime(bundle_path_file)
            if src_mtime <= bundle_cache_mtime:
                with open(bundle_path_file, "r", encoding="utf-8") as f:
                    bundle_path = f.read().strip()
                if bundle_path and os.path.exists(bundle_path):
                    needs_rebundle = False
    except Exception:
        pass

    if needs_rebundle:
        print("[ShortsPipeline] Bundling Remotion project...")
        bundle_cmd = [node_path, "remotion/bundle.mjs"]
        b_proc = subprocess.Popen(
            bundle_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1
        )
        for line in b_proc.stdout:
            print(line, end="")
            if line.startswith("BUNDLE_PATH:"):
                bundle_path = line.replace("BUNDLE_PATH:", "").strip()
        b_proc.wait()
        if b_proc.returncode != 0 or not bundle_path:
            raise RuntimeError("Remotion bundler failed")
        os.makedirs(os.path.dirname(bundle_path_file), exist_ok=True)
        with open(bundle_path_file, "w", encoding="utf-8") as f:
            f.write(bundle_path)

    # Copy assets into bundle public dir
    for asset_dir in ["broll_cache", "voiceovers", "music_cache", "music"]:
        src_dir = os.path.join("output", asset_dir)
        dest_dir = os.path.join(bundle_path, asset_dir)
        if os.path.exists(src_dir):
            os.makedirs(dest_dir, exist_ok=True)
            for fname in os.listdir(src_dir):
                src_file = os.path.join(src_dir, fname)
                dest_file = os.path.join(dest_dir, fname)
                if os.path.isfile(src_file) and not os.path.exists(dest_file):
                    shutil.copy2(src_file, dest_file)
                    
    # Rewrite absolute paths to bundle-relative paths for Remotion
    with open(data_path, "r", encoding="utf-8") as f:
        remotion_data = json.load(f)

    for clip in remotion_data.get("clips", []):
        clip["file"] = f"broll_cache/{os.path.basename(clip['file'])}"

    vo = remotion_data.get("voiceover_file", "")
    if vo and os.path.exists(vo):
        os.makedirs(os.path.join(bundle_path, "voiceovers"), exist_ok=True)
        shutil.copy2(vo, os.path.join(bundle_path, "voiceovers", os.path.basename(vo)))
        remotion_data["voiceover_file"] = f"voiceovers/{os.path.basename(vo)}"
    elif vo:
        remotion_data["voiceover_file"] = f"voiceovers/{os.path.basename(vo)}"

    at = remotion_data.get("audio_track", "")
    if at and os.path.exists(at):
        os.makedirs(os.path.join(bundle_path, "music_cache"), exist_ok=True)
        shutil.copy2(at, os.path.join(bundle_path, "music_cache", os.path.basename(at)))
        remotion_data["audio_track"] = f"music_cache/{os.path.basename(at)}"
    elif at:
        remotion_data["audio_track"] = f"music_cache/{os.path.basename(at)}"

    rel_data_path = data_path.replace(".json", "_relative.json")
    with open(rel_data_path, "w", encoding="utf-8") as f:
        json.dump(remotion_data, f, indent=2)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    cmd = [
        node_path, "remotion/render.mjs",
        "--composition", composition,
        "--data", rel_data_path,
        "--output", output_path,
        "--bundle", bundle_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Remotion render failed (exit {result.returncode}):\n"
            f"STDOUT: {result.stdout[-2000:]}\n"
            f"STDERR: {result.stderr[-2000:]}"
        )
    # Guard against silent failures (render.mjs may exit 0 even on some errors)
    if not os.path.exists(output_path):
        raise RuntimeError(
            f"Remotion exited 0 but output file not created: {output_path}\n"
            f"STDOUT: {result.stdout[-1000:]}\n"
            f"STDERR: {result.stderr[-1000:]}"
        )


def _validate_video(video_path: str) -> tuple[bool, str]:
    """Returns (ok, message). Checks size > 500KB and duration <= 58s."""
    if not os.path.exists(video_path):
        return False, "File does not exist"

    size_kb = os.path.getsize(video_path) / 1024
    if size_kb < 500:
        return False, f"File too small: {size_kb:.0f}KB (min 500KB)"

    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", video_path],
            capture_output=True, text=True, check=True,
        )
        duration = float(r.stdout.strip())
        if duration > 58.0:
            return False, f"Duration too long: {duration:.1f}s (max 58s)"
        return True, f"OK ({size_kb:.0f}KB, {duration:.1f}s)"
    except Exception as e:
        return False, f"ffprobe failed: {e}"


# ─── Legacy fallback render ───────────────────────────────────────────────────
def _legacy_render(item: dict, script: str, vo_path: str) -> str | None:
    """Fallback to MoviePy renderer for a single item. Returns video path or None."""
    try:
        from media.image_fetcher import ImageFetcher
        from media.video_shorts import VideoShortsGenerator
        from processors.rewrite_breaking import ScriptRewriter

        img_fetcher = ImageFetcher()
        vgen = VideoShortsGenerator()

        rewriter = ScriptRewriter()
        sentences = [s.strip() for s in script.split(".") if len(s.strip()) > 10]
        if not sentences:
            sentences = [item["headline"]]
        queries = [rewriter.generate_image_keywords(s) for s in sentences[:4]]
        image_paths = img_fetcher.fetch_multi_images(queries, f"img_{item['hash'][:8]}")

        video_path = f"output/videos/legacy_{item['hash'][:8]}.mp4"
        os.makedirs("output/videos", exist_ok=True)
        vgen.create_shorts(script, vo_path, video_path, image_paths=image_paths)
        return video_path
    except Exception as e:
        print(f"[ShortsPipeline] Legacy fallback also failed: {e}")
        return None


# ─── Per-item processing ──────────────────────────────────────────────────────
def _process_item(item: dict, dry_run: bool = False) -> bool:
    """Process a single breaking news item through the Remotion Shorts pipeline.
    Returns True if successful."""
    headline = item["headline"]
    slug = _make_slug(headline) + f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"\n[ShortsPipeline] Processing: {headline}")

    try:
        # a. Script
        rewriter = ScriptRewriter()
        script_text = rewriter.rewrite_for_shorts(headline, item.get("content", ""))
        script_text = rewriter.clean_script(script_text)

        # b. Hook + loop hook
        enhanced = enhance_shorts_script(script_text, headline)
        hook_text = enhanced["hook_text"]
        loop_hook = enhanced["loop_hook"]

        # c. Voiceover
        os.makedirs("output/voiceovers", exist_ok=True)
        vo_out = f"output/voiceovers/{slug}_vo.mp3"
        vo_path = generate_voiceover(script_text, vo_out, provider="hume")
        vo_dur = get_voiceover_duration(vo_path)

        # d. B-roll (6 clips, max 2s each)
        clips = _broll_for_headline(headline, n=6)

        # e. Caption chunks (already handled inside _assemble_remotion_data)

        # f. Music
        music_path = select_music("upbeat", vo_dur)
        # (may be None if no music available — handled gracefully)

        # g. Assemble payload
        remotion_data = _assemble_remotion_data(
            headline=headline,
            script_text=script_text,
            clips=clips,
            vo_path=vo_path,
            hook_text=hook_text,
            loop_hook=loop_hook,
            music_path=music_path,
        )

        # Save data file
        os.makedirs("output/remotion_data", exist_ok=True)
        data_path = f"output/remotion_data/{slug}.json"
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(remotion_data, f, indent=2, ensure_ascii=False)

        # h/i. Render
        video_out = f"output/renders/short_{slug}.mp4"
        os.makedirs("output/renders", exist_ok=True)

        render_ok = False
        try:
            _stream_render("ShortFormNews", data_path, video_out)
            render_ok = True
        except Exception as render_err:
            print(f"[ShortsPipeline] Remotion render failed: {render_err}")
            print("[ShortsPipeline] Falling back to legacy MoviePy renderer...")
            video_out = _legacy_render(item, script_text, vo_path)
            if not video_out:
                raise RuntimeError("Both Remotion and legacy render failed")

        # j. Validate
        valid, msg = _validate_video(video_out)
        if not valid:
            raise RuntimeError(f"Video validation failed: {msg}")
        print(f"[ShortsPipeline] Video validated: {msg}")

        # k. Upload
        if not dry_run:
            topic_tags = " ".join(
                f"#{w.lower()}" for w in headline.split()[:5]
                if len(w) > 3 and w.isalpha()
            )
            title = hook_text[:100]
            description = (
                f"{script_text}\n\n"
                f"#news #breaking #shorts {topic_tags}"
            )
            tags = [w for w in headline.split() if len(w) > 3 and w.isalpha()][:15]

            uploader = YouTubeUploader()
            yt_id = uploader.upload_video(
                video_out, title, description,
                tags=tags, category_id="25"
            )
            print(f"[ShortsPipeline] Uploaded: {yt_id}")
        else:
            dry_out = f"output/dry_run_upload_{slug}.json"
            with open(dry_out, "w") as f:
                json.dump({
                    "video_path": video_out,
                    "hook_text": hook_text,
                    "loop_hook": loop_hook,
                    "headline": headline,
                    "script_text": script_text[:200],
                }, f, indent=2)
            print(f"[ShortsPipeline] Dry run — saved to {dry_out}")

        return True

    except Exception as e:
        print(f"[ShortsPipeline] Item failed: {e}")
        return False


# ─── Main orchestrator ────────────────────────────────────────────────────────
def run_shorts_pipeline(dry_run: bool = False):
    print(f"=== Shorts Pipeline {'(DRY RUN) ' if dry_run else ''}===")

    posted_hashes = _load_posted()
    print(f"[ShortsPipeline] Loaded {len(posted_hashes)} posted hashes")

    # Fetch and classify
    fetcher = RSSFetcher(FEEDS)
    news_items = fetcher.fetch_all()
    classifier = NewsClassifier()
    breaking_news = classifier.filter_breaking(news_items)
    print(f"[ShortsPipeline] {len(breaking_news)} breaking news items found")

    processed = 0
    for item in breaking_news:
        if processed >= MAX_SHORTS_PER_RUN:
            print(f"[ShortsPipeline] Reached MAX_SHORTS_PER_RUN={MAX_SHORTS_PER_RUN}")
            break

        if item["hash"] in posted_hashes:
            print(f"[ShortsPipeline] Skipping already posted: {item['headline'][:60]}")
            continue

        success = _process_item(item, dry_run=dry_run)

        # l. Mark as posted (even on failure to avoid retry spam)
        posted_hashes.append(item["hash"])
        _save_posted(posted_hashes)

        if success:
            processed += 1
        else:
            print(f"[ShortsPipeline] Failed item marked to avoid retry: {item['headline'][:60]}")

    print(f"\n[ShortsPipeline] Done. Processed {processed}/{MAX_SHORTS_PER_RUN} items.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Remotion-based Shorts Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Skip YouTube upload")
    args = parser.parse_args()
    run_shorts_pipeline(dry_run=args.dry_run)
