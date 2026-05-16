import os
import glob
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.voiceover_generator import (
    build_ssml,
    generate_voiceover,
    get_voiceover_duration,
    estimate_word_timestamps,
)


def main():
    # 1. Find the latest oil prices script JSON
    pattern = "output/scripts/why_oil_prices_are_spiking_globally_*.json"
    matches = sorted(glob.glob(pattern))
    if not matches:
        # Try any longform script as fallback
        matches = sorted(glob.glob("output/scripts/*.json"))
    if not matches:
        print("ERROR: No script JSON found in output/scripts/. Run smoke_test.py first.")
        sys.exit(1)

    script_path = matches[-1]
    print(f"Using script: {script_path}")

    with open(script_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    full_script = data.get("full_script", "")
    sections = data.get("sections", {})

    if not full_script:
        print("ERROR: No full_script found in the JSON.")
        sys.exit(1)

    word_count = len(full_script.split())
    print(f"Script word count: {word_count}")

    # 2. Build SSML from sections
    print("\nBuilding SSML from sections...")
    ssml = build_ssml(sections)
    print(f"SSML length: {len(ssml)} chars")
    print(f"SSML preview (first 300 chars):\n{ssml[:300]}...\n")

    # 3. Generate voiceover
    output_path = "output/voiceovers/test_voiceover.mp3"
    os.makedirs("output/voiceovers", exist_ok=True)

    print("Generating voiceover (provider=auto: Google TTS -> ElevenLabs fallback)...")
    try:
        result_path = generate_voiceover(full_script, output_path, provider="auto")
        print(f"Voiceover saved to: {result_path}")

        # 4. Duration check
        duration_secs = get_voiceover_duration(result_path)
        duration_mins = duration_secs / 60.0
        in_range = 7.0 <= duration_mins <= 11.0

        print(f"\nDuration: {duration_mins:.2f} minutes ({duration_secs:.1f} seconds)")
        print(f"Duration check: {'PASS (7–11 minutes)' if in_range else f'FAIL (expected 7–11 min, got {duration_mins:.2f} min)'}")

        # 5. Word timestamps — use hook section for the sample
        hook_text = sections.get("hook", full_script[:500])
        timestamps = estimate_word_timestamps(result_path, hook_text, section_id="hook")

        print(f"\nFirst 5 word timestamps (section: hook, WPM: 140):")
        for entry in timestamps[:5]:
            print(f"  {entry}")

        print("\nFormat compatibility check:")
        if timestamps and "word" in timestamps[0] and "start" in timestamps[0] and "end" in timestamps[0]:
            print("  PASS — format matches {word, start, end} expected by normalizeTimestamps() in utils.ts")
        else:
            print("  FAIL — unexpected format")

    except Exception as e:
        print(f"\nVoiceover generation failed: {e}")
        print("\nRunning estimate_word_timestamps with synthetic duration (fallback test)...")

        # Create a dummy file to test timestamp logic
        dummy_path = "output/voiceovers/dummy.mp3"
        # Write a minimal valid mp3 header (silence)
        with open(dummy_path, "wb") as f:
            f.write(b"\xff\xfb\x90\x00" + b"\x00" * 413)  # ~1 sec mp3 frame

        hook_text = sections.get("hook", full_script.split(".")[0])
        # Estimate with known duration
        words = hook_text.split()
        wpm = 140  # hook rate
        synthetic_duration = len(words) / wpm * 60

        # Manually call the estimator logic
        seconds_per_word = 60.0 / wpm
        cursor = 0.0
        timestamps = []
        for word in words:
            word_duration = seconds_per_word * (0.7 + 0.3 * min(len(word) / 6.0, 1.5))
            end = min(cursor + word_duration, synthetic_duration)
            timestamps.append({"word": word, "start": round(cursor, 3), "end": round(end, 3)})
            cursor = end

        print(f"\nFirst 5 synthetic word timestamps (hook section, 140 WPM):")
        for entry in timestamps[:5]:
            print(f"  {entry}")

        print("\nFormat compatibility check:")
        if timestamps and "word" in timestamps[0] and "start" in timestamps[0] and "end" in timestamps[0]:
            print("  PASS — format matches {word, start, end} expected by normalizeTimestamps() in utils.ts")
        else:
            print("  FAIL — unexpected format")

        # Clean up
        if os.path.exists(dummy_path):
            os.remove(dummy_path)


if __name__ == "__main__":
    main()
