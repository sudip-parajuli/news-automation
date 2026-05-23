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
import math
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
from scripts.voiceover_generator import generate_voiceover, get_voiceover_duration, estimate_word_timestamps
from scripts.broll_fetcher import BRollFetcher
from scripts.caption_utils import build_caption_chunks
from scripts.music_selector import select_music, apply_music_ducking
from scripts.llm_utils import call_gemini
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


def _broll_queries_for_headline(headline: str, script_text: str, n: int = 6) -> list:
    """
    Use the LLM to generate n semantically meaningful, news-relevant Pexels video
    search queries from the headline and script. Falls back to simple noun extraction.
    Each query should be 2-4 concrete words that describe a real-world visual directly
    related to this specific news story.
    """
    system_prompt = (
        "You are a news video editor. Given a news headline and script, generate visually "
        "concrete Pexels search queries. Each query MUST be directly related to the story — "
        "use real locations, people types, organisations, or objects mentioned. "
        "NEVER use generic queries like 'breaking news', 'news report', or 'people talking'. "
        "Return ONLY a JSON array of strings, no markdown, no explanation."
    )
    user_prompt = (
        f"Headline: {headline}\n"
        f"Script: {script_text[:400]}\n\n"
        f"Generate exactly {n} distinct 2-4 word Pexels video search queries for b-roll. "
        f"Example for 'Air France crash verdict': "
        f'["airplane cockpit interior", "Paris courthouse exterior", "aircraft wreckage", '
        f'"courtroom judge", "airline passengers boarding", "family grief memorial"]\n'
        f"Return JSON array only."
    )
    try:
        raw = call_gemini(system_prompt, user_prompt, max_output_tokens=256)
        raw = raw.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0]
        import json as _json
        queries = _json.loads(raw.strip())
        if isinstance(queries, list) and len(queries) >= 1:
            # Ensure we have exactly n queries
            if len(queries) < n:
                queries = (queries * ((n // len(queries)) + 1))[:n]
            return [str(q).strip() for q in queries[:n]]
    except Exception as e:
        print(f"[ShortsPipeline] LLM b-roll query generation failed: {e}. Using fallback.")

    # Fallback: extract meaningful nouns/phrases from the headline
    stop_words = {"the", "a", "an", "and", "or", "but", "of", "in", "on",
                  "at", "to", "for", "is", "was", "are", "were", "over",
                  "with", "from", "that", "this", "about", "just", "found",
                  "what", "how", "why", "who", "they", "their", "have", "has"}
    words = [w for w in headline.split() if w.lower() not in stop_words and len(w) > 3]
    queries = []
    for i in range(n):
        start = (i * 2) % max(len(words), 1)
        phrase = " ".join(words[start : start + 3]) if len(words) >= 3 else headline[:40]
        queries.append(phrase)
    return queries


def _broll_for_headline(headline: str, script_text: str = "", n: int = 6) -> list:
    """
    Fetch `n` b-roll clips using BRollFetcher with LLM-generated semantic queries.
    Returns list of {"file": abs_path, "duration": float, "type": str, "label": str} for Remotion.
    """
    fetcher = BRollFetcher()
    queries = _broll_queries_for_headline(headline, script_text, n=n)
    print(f"[ShortsPipeline] B-roll queries: {queries}")

    clips = []
    for q in queries:
        try:
            broll = fetcher.fetch_broll(q)
            fp = os.path.abspath(broll["file_path"])
            duration = min(float(broll.get("duration", 5.0)), 2.0)
            clips.append({
                "file": fp,
                "duration": duration,
                "type": broll.get("type", "video"),
                "label": q.title().strip()
            })
        except Exception as e:
            print(f"[ShortsPipeline] B-roll fetch failed for '{q}': {e}")

    if not clips:
        print("[ShortsPipeline] WARNING: No b-roll fetched. Using empty clip list.")

    return clips


def _generate_highlight_card(script_text: str, timestamps: list) -> dict | None:
    """
    Extracts a key data visual or text visual (like a key statistic, fact, or short quote)
    from the script. Aligns it with the word timestamps to calculate start and end times in seconds.
    """
    if not timestamps:
        return None

    system_prompt = (
        "You are a news video graphic designer. Analyze the news script and identify exactly ONE key "
        "data point, statistic, fact, or statement that would be visually impactful to highlight as a card on screen. "
        "Choose a core piece of information.\n"
        "Return ONLY a JSON object with the following fields:\n"
        "- 'label': e.g., 'THE VERDICT' or 'TOTAL DAMAGE' or 'CASUALTIES' or 'STOCK RISE' (2-3 words in ALL CAPS)\n"
        "- 'value': e.g., 'Guilty' or '$4.5 Billion' or '85%' or '+12%' (1-3 words/numbers, NO emojis)\n"
        "- 'description': e.g., 'Air France found liable' or 'Estimated cost of repairs' (short sentence, max 6 words)\n"
        "- 'keyword': a specific word in the script that marks when this highlight is mentioned. Choose a word that is unique or appears exactly where this information is discussed.\n"
        "- 'duration_words': integer, how many words' duration this card should stay visible (typically 6 to 12 words).\n\n"
        "Return JSON only. No explanation, no markdown."
    )
    
    user_prompt = (
        f"Script: {script_text}\n\n"
        "Identify the single most impactful fact or metric. Return JSON object."
    )
    
    try:
        raw = call_gemini(system_prompt, user_prompt, max_output_tokens=256)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0]
        
        card_data = json.loads(raw.strip())
        keyword = str(card_data.get("keyword", "")).strip().lower()
        duration_words = int(card_data.get("duration_words", 8))
        
        # Clean keyword (remove punctuation)
        clean_keyword = re.sub(r"[^\w]", "", keyword)
        
        # Find the word index of the keyword in timestamps
        keyword_idx = -1
        for idx, entry in enumerate(timestamps):
            entry_word = re.sub(r"[^\w]", "", entry["word"].lower())
            if entry_word == clean_keyword:
                keyword_idx = idx
                break
                
        # If we couldn't find the keyword, look for a partial match
        if keyword_idx == -1:
            for idx, entry in enumerate(timestamps):
                if clean_keyword in re.sub(r"[^\w]", "", entry["word"].lower()):
                    keyword_idx = idx
                    break
        
        # If still not found, default to 1/3 of the script duration
        if keyword_idx == -1:
            keyword_idx = max(0, len(timestamps) // 3)
            
        # Determine start and end times
        start_time = float(timestamps[keyword_idx]["start"])
        end_idx = min(keyword_idx + duration_words, len(timestamps) - 1)
        end_time = float(timestamps[end_idx].get("end", start_time + 3.0))
        
        return {
            "label": str(card_data.get("label", "HIGHLIGHT")).upper(),
            "value": str(card_data.get("value", "")),
            "description": str(card_data.get("description", "")),
            "startTime": round(start_time, 2),
            "endTime": round(end_time, 2)
        }
    except Exception as e:
        print(f"[ShortsPipeline] Highlight card generation failed: {e}")
        return None


def _assemble_remotion_data(
    headline: str,
    script_text: str,
    clips: list,
    vo_path: str,
    hook_text: str,
    loop_hook: str,
    music_path: str | None,
    timestamps: list | None = None,
    voiceover_duration_seconds: float | None = None,
    highlight_card: dict | None = None,
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
        "timestamps": timestamps or [],
        "voiceover_duration_seconds": voiceover_duration_seconds or 0,
        "highlight_card": highlight_card,
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

        # c2. Word-level timestamps for caption burn-in
        try:
            timestamps = estimate_word_timestamps(vo_path, script_text)
        except Exception as ts_err:
            print(f"[ShortsPipeline] Timestamp estimation failed: {ts_err}. Captions may be inaccurate.")
            timestamps = []

        # Determine dynamic clip count: num_clips = max(4, min(15, ceil((vo_dur + 3.5) / 2.0)))
        num_clips = max(4, min(15, int(math.ceil((vo_dur + 3.5) / 2.0))))
        print(f"[ShortsPipeline] Voiceover duration: {vo_dur}s. Fetching {num_clips} clips.")

        # d. B-roll (dynamic clips count) — uses LLM semantic queries
        clips = _broll_for_headline(headline, script_text=script_text, n=num_clips)

        # Generate highlight card if timestamps are available
        highlight_card = _generate_highlight_card(script_text, timestamps)
        if highlight_card:
            print(f"[ShortsPipeline] Generated highlight card: {highlight_card}")

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
            timestamps=timestamps,
            voiceover_duration_seconds=vo_dur,
            highlight_card=highlight_card,
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
