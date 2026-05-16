import os
import sys
import glob
import subprocess
import tempfile
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.music_selector import select_music, apply_music_ducking
from scripts.voiceover_generator import get_voiceover_duration


def make_silence(path: str, duration: int = 30):
    """Generate a silent mp3 file of the given duration as a stand-in voiceover."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "anullsrc=r=44100:cl=stereo",
            "-t", str(duration),
            "-q:a", "9",
            "-acodec", "libmp3lame",
            path,
        ],
        check=True,
        capture_output=True,
    )


def main():
    print("=== Phase 8 Music Smoke Test ===\n")

    # 1. Find or create a voiceover stand-in
    existing = sorted(glob.glob("output/voiceovers/*.mp3"))
    if existing:
        voiceover_path = existing[-1]
        print(f"Using existing voiceover: {voiceover_path}")
    else:
        voiceover_path = "output/voiceovers/silence_standin.mp3"
        print(f"No voiceover found. Generating 30s silence stand-in: {voiceover_path}")
        make_silence(voiceover_path, 30)

    voiceover_duration = get_voiceover_duration(voiceover_path)
    print(f"Voiceover duration: {voiceover_duration:.2f}s\n")

    # 2. Select music (calm mood — expect placeholder warning)
    print("Selecting music for mood='calm'...")
    music_path = select_music("calm", voiceover_duration)
    print(f"Selected track: {music_path}\n")

    # 3. Apply ducking
    output_path = "output/voiceovers/mixed_output.mp3"
    print(f"Applying music ducking -> {output_path}")
    apply_music_ducking(voiceover_path, music_path, output_path)
    print("Done.\n")

    # 4. Duration check (±1 second tolerance)
    mixed_duration = get_voiceover_duration(output_path)
    diff = abs(mixed_duration - voiceover_duration)
    passed = diff <= 1.0

    print(f"Voiceover duration : {voiceover_duration:.2f}s")
    print(f"Mixed output duration: {mixed_duration:.2f}s")
    print(f"Difference         : {diff:.2f}s")
    print(f"Duration match check: {'PASS (within ±1s)' if passed else f'FAIL (diff={diff:.2f}s)'}")

    if passed:
        print("\n--- SMOKE TEST PASSED ---")
    else:
        print("\n--- SMOKE TEST FAILED ---")
        sys.exit(1)


if __name__ == "__main__":
    main()
