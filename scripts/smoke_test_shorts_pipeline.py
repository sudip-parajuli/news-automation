import os
import sys
import json
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from processors.rewrite_breaking import ScriptRewriter
from scripts.shorts_script_enhancer import enhance_shorts_script
from scripts.voiceover_generator import generate_voiceover, get_voiceover_duration
from scripts.shorts_pipeline import _broll_for_headline, _assemble_remotion_data, _stream_render, _validate_video
from scripts.music_selector import select_music

def run_smoke_test():
    print("=== Starting Shorts Pipeline Smoke Test ===")
    
    test_item = {
        "headline": "Earthquake triggers tsunami warning for millions",
        "content": "A massive 8.0 magnitude earthquake struck the Pacific coast today, prompting immediate tsunami warnings for millions of residents. Authorities are urging immediate evacuation of low-lying areas. The tremors were felt for hundreds of miles, causing significant structural damage to several coastal cities. Emergency services have been deployed to assess the situation and provide aid.",
        "hash": "test12345"
    }

    try:
        # 1. Script Rewriter
        rewriter = ScriptRewriter()
        script_text = rewriter.rewrite_for_shorts(test_item["headline"], test_item["content"])
        script_text = rewriter.clean_script(script_text)
        print("[PASS] Script rewritten successfully.")
        
        # 2. Hook and Loop Hook
        enhanced = enhance_shorts_script(script_text, test_item["headline"])
        hook_text = enhanced["hook_text"]
        loop_hook = enhanced["loop_hook"]
        print(f"[PASS] hook_text: {hook_text!r}")
        print(f"[PASS] loop_hook: {loop_hook!r}")
        
        # 3. Voiceover
        os.makedirs("output/voiceovers", exist_ok=True)
        vo_out = "output/voiceovers/test_short_vo.mp3"
        
        if not os.getenv("HUME_VOICE_ID"):
            print("[WARN] HUME_VOICE_ID is not set. Creating a mock silent voiceover.")
            # Create a valid silent mp3 using ffmpeg (10 seconds)
            import subprocess
            if os.path.exists(vo_out):
                os.remove(vo_out)
            subprocess.run(["ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "10", "-q:a", "9", "-acodec", "libmp3lame", vo_out, "-y"], capture_output=True)
            vo_path = vo_out
        else:
            vo_path = generate_voiceover(script_text, vo_out, provider="hume")

        if not os.path.exists(vo_path) or os.path.getsize(vo_path) == 0:
            raise RuntimeError("Voiceover generation failed or file is empty.")
        vo_dur = get_voiceover_duration(vo_path)
        size_kb = os.path.getsize(vo_path) / 1024
        print(f"[PASS] Voiceover: {vo_path} ({size_kb:.1f} KB, {vo_dur}s)")
        
        # 4. B-roll
        clips = _broll_for_headline(test_item["headline"], n=6)
        if len(clips) != 6:
            print(f"[WARN] B-roll fetched {len(clips)} clips instead of 6.")
        else:
            print(f"[PASS] B-roll: {len(clips)} clips fetched.")
            
        # 5. Music
        music_path = select_music("upbeat", vo_dur)
        if music_path:
            print(f"[PASS] Music selected: {music_path}")
        else:
            print("[PASS] No music selected (None returned).")
            
        # 6. Assemble
        remotion_data = _assemble_remotion_data(
            headline=test_item["headline"],
            script_text=script_text,
            clips=clips,
            vo_path=vo_path,
            hook_text=hook_text,
            loop_hook=loop_hook,
            music_path=music_path
        )
        os.makedirs("output/remotion_data", exist_ok=True)
        data_path = "output/remotion_data/test_short.json"
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(remotion_data, f, indent=2)
        print("[PASS] Remotion payload assembled.")

        # 7. Remotion Render pre-check
        if not os.path.exists("remotion/node_modules"):
            print("[SKIP] Remotion render skipped: remotion/node_modules not found. Run 'npm install' in remotion/ first.")
            return

        print("Testing Remotion render... this may take a minute...")
        video_out = "output/renders/test_short.mp4"
        if os.path.exists(video_out):
            os.remove(video_out)
            
        _stream_render("ShortFormNews", data_path, video_out)
        
        # 8. Validation
        valid, msg = _validate_video(video_out)
        if valid:
            print(f"[PASS] Remotion render: {os.path.basename(video_out)} is valid. {msg}")
        else:
            raise RuntimeError(f"Video validation failed: {msg}")
            
    except Exception as e:
        print(f"\n[FAIL] Smoke test failed: {e}")
        sys.exit(1)

    print("\n=== Smoke Test Completed Successfully ===")

if __name__ == "__main__":
    run_smoke_test()
