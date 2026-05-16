import os
import json
import random
import subprocess
import tempfile
import httpx
from pathlib import Path

# ─── Constants ────────────────────────────────────────────────────────────────
MUSIC_DIR = Path(__file__).parent.parent / "assets" / "music"
CATALOG_PATH = MUSIC_DIR / "catalog.json"

SECTION_MOOD_MAP = {
    "hook":       "calm",
    "context":    "calm",
    "conflict":   "tense",
    "evidence":   "tense",
    "twist":      "dramatic",
    "resolution": "calm",
    "cta":        "upbeat",
}


# ─── Public API ───────────────────────────────────────────────────────────────
def get_mood_for_section(section_id: str) -> str:
    """Return the appropriate music mood for a given script section ID."""
    return SECTION_MOOD_MAP.get(section_id.lower(), "calm")


# ─── Pixabay API ──────────────────────────────────────────────────────────────
def fetch_pixabay_music(mood: str, duration_seconds: float = 0.0) -> str:
    api_key = os.getenv("PIXABAY_API_KEY")
    if not api_key:
        raise ValueError("PIXABAY_API_KEY is not set")

    pixabay_mood = {
        "calm": "calm",
        "tense": "dark",
        "dramatic": "cinematic",
        "upbeat": "upbeat"
    }.get(mood.lower(), "calm")

    # Correct endpoint: /api/ with type=music (NOT /api/videos/music/)
    url = (
        f"https://pixabay.com/api/"
        f"?key={api_key}&q={pixabay_mood}&type=music"
        f"&per_page=5&safesearch=true"
    )

    response = httpx.get(url, timeout=30.0)
    response.raise_for_status()
    data = response.json()

    if "hits" not in data or not data["hits"]:
        raise ValueError(f"No Pixabay music found for mood: {pixabay_mood}")

    # Find a hit that actually has a playable audio URL
    audio_url = None
    track_id = None
    for hit in data["hits"]:
        # Pixabay audio tracks have a 'webformatURL' or embedded audio link
        url_candidate = (
            hit.get("audio") or
            hit.get("userImageURL") or
            hit.get("previewURL")
        )
        # The actual audio file is available via the pageURL for music type;
        # we use the direct MP3 stream from Pixabay's CDN via webformatURL on audio type
        # Fall through to local if no direct link is available
        if url_candidate and url_candidate.endswith(".mp3"):
            audio_url = url_candidate
            track_id = str(hit.get("id", "0"))
            break

    if not audio_url:
        raise ValueError("Pixabay music response has no direct MP3 URL — API may require a different plan")

    cache_dir = Path("output/music_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_path = cache_dir / f"{mood}_{track_id}.mp3"

    if not out_path.exists():
        print(f"Downloading Pixabay music (id: {track_id}) to {out_path}...")
        r = httpx.get(audio_url, timeout=60.0)
        r.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(r.content)

    return str(out_path)

def select_music(mood: str, duration_seconds: float = 0.0) -> str:
    """
    Select a music track matching the requested mood.
    Attempts to fetch from Pixabay first (3 retries).
    Falls back to local placeholders if API fails.
    Returns the absolute path to the selected track.
    """
    # 1. Try Pixabay API
    for attempt in range(3):
        try:
            return fetch_pixabay_music(mood, duration_seconds)
        except Exception as e:
            print(f"Pixabay fetch attempt {attempt+1} failed: {e}")
            
    print(f"WARNING: Falling back to local music catalog for mood '{mood}'")
    
    # 2. Fallback to local catalog
    if not CATALOG_PATH.exists():
        print(f"WARNING: Music catalog not found at {CATALOG_PATH} — skipping music")
        return None

    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    tracks = catalog.get("tracks", [])
    mood_tracks = [t for t in tracks if t.get("mood") == mood]

    if not mood_tracks:
        print(f"WARNING: No tracks found for mood '{mood}'. Using any available track.")
        mood_tracks = tracks

    if not mood_tracks:
        print("WARNING: No tracks in catalog — skipping music")
        return None

    # Pick a random match that actually exists on disk
    random.shuffle(mood_tracks)
    for selected in mood_tracks:
        candidate = MUSIC_DIR / selected["file"]
        if candidate.exists():
            return str(candidate)

    print(f"WARNING: All catalog tracks for mood '{mood}' are missing from disk — skipping music")
    return None


def apply_music_ducking(
    voiceover_path: str,
    music_path: str,
    output_path: str,
) -> str:
    """
    Mix voiceover and background music with ducking via a two-step FFmpeg process.

    Step 1: Loop music to match voiceover duration (stream_loop flag BEFORE -i).
    Step 2: Mix with aeval filter at 12% music volume.
    Step 3: Delete temp looped file.

    Returns path to the mixed output mp3.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # Get voiceover duration
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            voiceover_path,
        ],
        capture_output=True, text=True, check=True,
    )
    duration = float(result.stdout.strip())

    tmp_dir = tempfile.mkdtemp()
    looped_music = os.path.join(tmp_dir, "looped_music.mp3")

    try:
        # Step 1: Loop music to voiceover duration
        # -stream_loop MUST come before -i (critical on Windows FFmpeg builds)
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-stream_loop", "-1",
                "-i", music_path,
                "-t", str(duration),
                "-c", "copy",
                looped_music,
            ],
            check=True,
            capture_output=True,
        )

        # Step 2: Mix with aeval ducking filter (music permanently at 12%)
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", voiceover_path,
                "-i", looped_music,
                "-filter_complex",
                "[1:a]aeval=val(0)*0.12:c=same[music_low];"
                "[0:a][music_low]amix=inputs=2:duration=first:dropout_transition=0",
                "-ac", "2",
                output_path,
            ],
            check=True,
            capture_output=True,
        )

    finally:
        # Step 3: Clean up temp files
        if os.path.exists(looped_music):
            os.remove(looped_music)
        if os.path.exists(tmp_dir):
            try:
                os.rmdir(tmp_dir)
            except OSError:
                pass  # Non-empty dir — skip, it'll be GC'd

    return output_path
