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
def is_valid_audio(file_path: str) -> bool:
    """Check if the given file is a valid, readable audio file using ffprobe."""
    try:
        subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            check=True,
            capture_output=True,
        )
        return True
    except Exception:
        return False

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
        # Pixabay audio tracks have an 'audio' or embedded link.
        url_candidate = (
            hit.get("audio") or
            hit.get("preview_url") or
            hit.get("audio_url") or
            hit.get("previewURL")
        )
        if url_candidate and isinstance(url_candidate, str):
            audio_url = url_candidate
            track_id = str(hit.get("id", "0"))
            break

    if not audio_url:
        raise ValueError("Pixabay music response has no direct MP3 URL — API may require a different plan")

    cache_dir = Path("output/music_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_path = cache_dir / f"{mood}_{track_id}.mp3"

    # If the file exists but is corrupted (e.g. holds HTML error text), delete it
    if out_path.exists() and not is_valid_audio(str(out_path)):
        print(f"WARNING: Cached music {out_path} is corrupted. Deleting to re-download...")
        try:
            out_path.unlink()
        except OSError:
            pass

    if not out_path.exists():
        print(f"Downloading Pixabay music (id: {track_id}) to {out_path}...")
        r = httpx.get(audio_url, timeout=60.0)
        r.raise_for_status()
        
        # Check Content-Type to make sure we didn't receive a Cloudflare captcha/HTML page
        content_type = r.headers.get("content-type", "").lower()
        if "html" in content_type or "text" in content_type:
            raise ValueError("Pixabay returned HTML/text instead of binary audio (Cloudflare/IP block)")

        with open(out_path, "wb") as f:
            f.write(r.content)

        # Confirm downloaded file is actually readable by FFmpeg
        if not is_valid_audio(str(out_path)):
            try:
                out_path.unlink()
            except OSError:
                pass
            raise ValueError("Downloaded Pixabay file is not a valid audio file.")

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
    Mix voiceover and background music with ducking using a robust process:
    1. Decode the input music (e.g., MP3) to a temporary uncompressed WAV file.
       (Crucial for preventing -stream_loop demuxer issues on MP3s).
    2. Mix the voiceover and looped WAV in one FFmpeg command using amix=duration=first.
    3. Clean up the temporary WAV file.
    
    Returns path to the mixed output mp3.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    tmp_dir = tempfile.mkdtemp()
    decoded_wav = os.path.join(tmp_dir, "decoded_music.wav")

    try:
        # Step 1: Decode to temporary WAV (lossless, easy for FFmpeg to seek and loop)
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", music_path,
                "-c:a", "pcm_s16le",
                decoded_wav,
            ],
            check=True,
            capture_output=True,
        )

        # Step 2: Mix voiceover with the looped WAV
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-stream_loop", "-1",
                "-i", decoded_wav,
                "-i", voiceover_path,
                "-filter_complex",
                "[0:a]aeval=val(0)*0.12[music_low];"
                "[1:a][music_low]amix=inputs=2:duration=first:dropout_transition=0",
                "-ac", "2",
                output_path,
            ],
            check=True,
            capture_output=True,
        )

    finally:
        # Step 3: Clean up temp files
        if os.path.exists(decoded_wav):
            os.remove(decoded_wav)
        if os.path.exists(tmp_dir):
            try:
                os.rmdir(tmp_dir)
            except OSError:
                pass

    return output_path
