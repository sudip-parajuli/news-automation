import os
import re
import json
import base64
import subprocess
import tempfile
import httpx
import time
from dotenv import load_dotenv
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

load_dotenv()

# ─── Per-section WPM rates ────────────────────────────────────────────────────
SECTION_WPM = {
    "hook":       140,
    "context":    165,
    "conflict":   170,
    "evidence":   165,
    "twist":      150,
    "resolution": 160,
    "cta":        185,
}
DEFAULT_WPM = 160

SECTION_ORDER = ["hook", "context", "conflict", "evidence", "twist", "resolution", "cta"]


# ─── Retry decorator (same pattern as Phase 3/4) ─────────────────────────────
def llm_retry_decorator():
    return retry(
        wait=wait_exponential(min=2, max=30),
        stop=stop_after_attempt(6),
        reraise=True,
        retry=retry_if_exception_type((Exception,)),
    )


# ─── SSML builder ─────────────────────────────────────────────────────────────
def build_ssml(sections: dict) -> str:
    """
    Builds a full SSML document from the structured sections dict output by
    longform_script_generator.py.

    Rules:
    - <break time="600ms"/> between all sections
    - First sentence of 'hook' wrapped in <emphasis level="strong">
    - 'cta' section wrapped in <prosody rate="fast">
    - All other sections use plain <p> tags
    """
    parts = ['<speak>']

    for i, section_id in enumerate(SECTION_ORDER):
        text = sections.get(section_id, "").strip()
        if not text:
            continue

        if i > 0:
            parts.append('<break time="600ms"/>')

        if section_id == "hook":
            # Emphasise the first sentence only
            sentences = re.split(r'(?<=[.!?])\s+', text, maxsplit=1)
            first = sentences[0].strip()
            rest = sentences[1].strip() if len(sentences) > 1 else ""
            hook_content = f'<emphasis level="strong">{first}</emphasis>'
            if rest:
                hook_content += f' {rest}'
            parts.append(f'<p>{hook_content}</p>')

        elif section_id == "cta":
            parts.append(f'<prosody rate="fast"><p>{text}</p></prosody>')

        else:
            parts.append(f'<p>{text}</p>')

    parts.append('</speak>')
    return '\n'.join(parts)


# ─── Hume AI TTS ─────────────────────────────────────────────────────────────
class HumeKeyRotator:
    def __init__(self):
        self.keys = []
        for i in ["", "2", "3", "4", "5", "6", "7", "8", "9", "10"]:
            key = os.getenv(f"HUME_API_KEY{i}")
            if key:
                self.keys.append({"key": key, "cooldown_until": 0.0, "index": i or "1"})
        
        # We don't raise error on init to avoid breaking non-TTS tasks if env isn't fully set,
        # but we will fail when get_key() is called if empty.
        self.current_idx = 0
        
    def get_key(self):
        if not self.keys:
            raise ValueError("No HUME_API_KEYs found in environment")
            
        start_idx = self.current_idx
        while True:
            k_info = self.keys[self.current_idx]
            if time.time() >= k_info["cooldown_until"]:
                key = k_info["key"]
                idx_name = k_info["index"]
                self.current_idx = (self.current_idx + 1) % len(self.keys)
                return key, idx_name
                
            self.current_idx = (self.current_idx + 1) % len(self.keys)
            if self.current_idx == start_idx:
                earliest = min(k["cooldown_until"] for k in self.keys)
                wait_time = earliest - time.time()
                if wait_time > 86400: # more than a day
                    raise Exception("All Hume API keys are permanently exhausted (out of credits).")
                if wait_time > 0:
                    print(f"All Hume keys rate limited. Waiting {wait_time:.1f}s...")
                    time.sleep(wait_time)

    def mark_cooldown(self, key_val):
        for k in self.keys:
            if k["key"] == key_val:
                k["cooldown_until"] = time.time() + 60.0
                break

    def mark_timeout(self, key_val):
        """Mark a key as timed-out with a shorter 30s cooldown (transient issue)."""
        for k in self.keys:
            if k["key"] == key_val:
                k["cooldown_until"] = time.time() + 30.0
                print(f"Hume key #{k['index']} marked for 30s timeout cooldown")
                break

rotator = HumeKeyRotator()

@llm_retry_decorator()
def _call_hume_tts(text: str, output_path: str, chunk_index: int, total_chunks: int) -> str:
    voice_id = os.getenv("HUME_VOICE_ID")
    if not voice_id:
        raise ValueError("HUME_VOICE_ID is not set")
        
    key, idx_name = rotator.get_key()
    print(f"TTS chunk {chunk_index}/{total_chunks} via key #{idx_name}")
    
    url = "https://api.hume.ai/v0/tts"
    headers = {
        "X-Hume-Api-Key": key,
        "Content-Type": "application/json"
    }
    payload = {
        "utterances": [{"text": text, "voice": {"id": voice_id}}],
        "format": {"type": "mp3"}
    }
    
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=120.0)
    except (httpx.ReadTimeout, httpx.ConnectTimeout) as e:
        rotator.mark_timeout(key)
        raise  # tenacity will retry with the next key

    if response.status_code == 429:
        rotator.mark_cooldown(key)
        raise Exception(f"Hume API rate limited (429) for key #{idx_name}")
        
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        print(f"Hume API Error [{response.status_code}] on key #{idx_name}: {response.text}")
        if response.status_code == 400 and ("credit" in response.text.lower() or "fund" in response.text.lower()):
            print(f"Key #{idx_name} is out of credits. Removing from rotation.")
            # We can mark it with a very long cooldown
            rotator.mark_cooldown(key)
            # Actually, let's just make it a year
            for k in rotator.keys:
                if k["key"] == key:
                    k["cooldown_until"] = time.time() + 31536000.0
                    break
        raise
        
    data = response.json()
    
    audio_b64 = data["generations"][0]["audio"]
    audio_bytes = base64.b64decode(audio_b64)
    with open(output_path, "wb") as f:
        f.write(audio_bytes)
    return output_path



# ─── Chunked generation + FFmpeg concat ──────────────────────────────────────
def _split_into_chunks(text: str, max_chars: int = 1500) -> list[str]:
    """Split text at sentence boundaries keeping each chunk ≤ max_chars."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= max_chars:
            current = (current + " " + sentence).strip()
        else:
            if current:
                chunks.append(current)
            current = sentence

    if current:
        chunks.append(current)

    return chunks


def _concat_audio_files(chunk_paths: list[str], output_path: str):
    """Concatenate mp3 files using FFmpeg concat list file (Windows-safe)."""
    concat_list = output_path + "_concat.txt"
    try:
        with open(concat_list, "w", encoding="utf-8") as f:
            for p in chunk_paths:
                # FFmpeg requires forward slashes even on Windows inside list file
                safe_path = p.replace("\\", "/")
                f.write(f"file '{safe_path}'\n")

        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", concat_list,
                "-acodec", "copy",
                output_path,
            ],
            check=True,
            capture_output=True,
        )
    finally:
        if os.path.exists(concat_list):
            os.remove(concat_list)


def generate_voiceover(
    script_text: str,
    output_path: str,
    provider: str = "hume",
) -> str:
    """
    Generate a voiceover mp3 for the given script text.
    Returns path to the final audio file.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    chunks = _split_into_chunks(script_text)

    if len(chunks) == 1:
        return _generate_chunk(chunks[0], output_path, provider, chunk_index=1, total_chunks=1)

    chunk_paths = []
    tmp_dir = tempfile.mkdtemp()
    try:
        for i, chunk in enumerate(chunks):
            chunk_path = os.path.join(tmp_dir, f"chunk_{i:03d}.mp3")
            _generate_chunk(chunk, chunk_path, provider, chunk_index=i+1, total_chunks=len(chunks))
            chunk_paths.append(chunk_path)

        _concat_audio_files(chunk_paths, output_path)
    finally:
        for p in chunk_paths:
            if os.path.exists(p):
                os.remove(p)
        if os.path.exists(tmp_dir):
            os.rmdir(tmp_dir)

    return output_path


def _generate_chunk(text: str, output_path: str, provider: str, chunk_index: int = 1, total_chunks: int = 1) -> str:
    """Generate audio for a single text chunk using Hume AI."""
    return _call_hume_tts(text, output_path, chunk_index, total_chunks)


def generate_voiceover_from_ssml(ssml: str, output_path: str) -> str:
    """Generate voiceover directly from a pre-built SSML string (legacy)."""
    raise NotImplementedError("SSML generation is not supported with Hume AI.")


# ─── Duration via ffprobe ─────────────────────────────────────────────────────
def get_voiceover_duration(audio_path: str) -> float:
    """Returns the duration of an audio file in seconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


# ─── Word timestamp estimator ─────────────────────────────────────────────────
def estimate_word_timestamps(
    audio_path: str,
    script_text: str,
    section_id: str = "context",
) -> list[dict]:
    """
    Estimates word-level timestamps using per-section WPM rates.
    Returns [{word, start, end}, ...] — compatible with normalizeTimestamps() in utils.ts.
    """
    duration = get_voiceover_duration(audio_path)
    words = script_text.split()
    if not words:
        return []

    wpm = SECTION_WPM.get(section_id.lower(), DEFAULT_WPM)
    seconds_per_word = 60.0 / wpm

    timestamps = []
    cursor = 0.0

    for word in words:
        # Scale word duration by character length (longer words take slightly longer)
        word_duration = seconds_per_word * (0.7 + 0.3 * min(len(word) / 6.0, 1.5))
        end = min(cursor + word_duration, duration)
        timestamps.append({
            "word": word,
            "start": round(cursor, 3),
            "end": round(end, 3),
        })
        cursor = end

    return timestamps
