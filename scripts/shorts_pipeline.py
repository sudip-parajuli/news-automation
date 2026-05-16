import os
import re
import sys
import glob
import json
import shutil
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from scripts.longform_script_generator import LongformScriptGenerator
from scripts.broll_fetcher import BRollFetcher
from scripts.voiceover_generator import generate_voiceover, get_voiceover_duration
from scripts.music_selector import select_music, apply_music_ducking, get_mood_for_section
from uploader.youtube_uploader import YouTubeUploader
from scripts.caption_utils import build_caption_chunks

def _make_slug(topic: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', topic.lower()).strip('_')

def _build_remotion_data(script_data: dict, broll_dict: dict, voiceover_path: str, music_path: str, hook_text: str) -> dict:
    sections = []
    for section_id in ["hook", "context", "conflict", "evidence", "twist", "resolution", "cta"]:
        text = script_data.get("sections", {}).get(section_id, "")
        if not text:
            continue
            
        broll_list = broll_dict.get(section_id, [])
        abs_broll = []
        for b in broll_list:
            b_copy = dict(b)
            if not os.path.isabs(b_copy["file_path"]):
                b_copy["file_path"] = os.path.abspath(b_copy["file_path"])
                
            if "duration_seconds" in b_copy:
                b_copy["duration"] = b_copy.pop("duration_seconds")
                
            abs_broll.append(b_copy)
            
        # Add caption chunks for the section
        words = text.split()
        chunks = build_caption_chunks(words)
        
        sections.append({
            "id": section_id,
            "text": text,
            "broll": abs_broll,
            "caption_chunks": chunks
        })
        
    abs_vo = os.path.abspath(voiceover_path) if voiceover_path and not os.path.isabs(voiceover_path) else voiceover_path
    abs_music = os.path.abspath(music_path) if music_path and not os.path.isabs(music_path) else music_path
        
    return {
        "title": script_data.get("topic", ""),
        "hook_text": hook_text,
        "sections": sections,
        "voiceover_file": abs_vo,
        "background_music": abs_music
    }

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
            os.path.getmtime("remotion/src/compositions")
        )
        if os.path.exists(bundle_path_file):
            bundle_cache_mtime = os.path.getmtime(bundle_path_file)
            if src_mtime <= bundle_cache_mtime:
                with open(bundle_path_file, "r", encoding="utf-8") as f:
                    bundle_path = f.read().strip()
                if bundle_path and os.path.exists(bundle_path):
                    needs_rebundle = False
    except Exception as e:
        pass
        
    if needs_rebundle:
        bundle_cmd = [node_path, "remotion/bundle.mjs"]
        b_proc = subprocess.Popen(bundle_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        
        for line in b_proc.stdout:
            if line.startswith("BUNDLE_PATH:"):
                bundle_path = line.replace("BUNDLE_PATH:", "").strip()
        
        b_proc.wait()
        if b_proc.returncode != 0 or not bundle_path:
            raise RuntimeError(f"Remotion bundler failed")
            
        os.makedirs(os.path.dirname(bundle_path_file), exist_ok=True)
        with open(bundle_path_file, "w", encoding="utf-8") as f:
            f.write(bundle_path)
            
    for asset_dir in ["broll_cache", "voiceovers", "music"]:
        src_dir = os.path.join("output", asset_dir)
        dest_dir = os.path.join(bundle_path, asset_dir)
        if os.path.exists(src_dir):
            os.makedirs(dest_dir, exist_ok=True)
            for file_name in os.listdir(src_dir):
                src_file = os.path.join(src_dir, file_name)
                dest_file = os.path.join(dest_dir, file_name)
                if os.path.isfile(src_file) and not os.path.exists(dest_file):
                    shutil.copy2(src_file, dest_file)

    with open(data_path, "r", encoding="utf-8") as f:
        remotion_data = json.load(f)
        
    for section in remotion_data.get("sections", []):
        for b in section.get("broll", []):
            fname = os.path.basename(b["file_path"])
            b["file_path"] = f"broll_cache/{fname}"
            
    vo_path = remotion_data.get("voiceover_file", "")
    if vo_path:
        remotion_data["voiceover_file"] = f"voiceovers/{os.path.basename(vo_path)}"
        
    music_path = remotion_data.get("background_music", "")
    if music_path:
        remotion_data["background_music"] = f"music/{os.path.basename(music_path)}"
        
    updated_data_path = data_path.replace(".json", "_relative.json")
    with open(updated_data_path, "w", encoding="utf-8") as f:
        json.dump(remotion_data, f, indent=2)
        
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    cmd = [
        node_path, 
        "remotion/render.mjs", 
        "--composition", composition,
        "--data", updated_data_path,
        "--output", output_path,
        "--bundle", bundle_path
    ]
    
    process = subprocess.run(cmd, capture_output=True, text=True)
    if process.returncode != 0:
        raise RuntimeError(f"Remotion render failed: {process.stdout} {process.stderr}")

def run_shorts_pipeline(topic: str, dry_run: bool = False):
    print(f"=== Starting Shorts Pipeline {'(DRY RUN)' if dry_run else ''} ===")
    slug = _make_slug(topic) + f"_shorts_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    try:
        # Step 1: Script
        print("--- Step 1: Script Generation ---")
        script_gen = LongformScriptGenerator()
        script_data = script_gen.generate_script(topic)
        context_text = script_data.get("sections", {}).get("context", "")
        hook_text = script_gen.generate_hook_for_shorts(context_text)

        # Step 2: B-Roll
        print("\n--- Step 2: B-Roll Fetch ---")
        fetcher = BRollFetcher()
        broll_dict = fetcher.fetch_broll_for_script(script_data.get("sections", {}))

        # Step 3: Voiceover
        print("\n--- Step 3: Voiceover ---")
        os.makedirs("output/voiceovers", exist_ok=True)
        vo_out_path = f"output/voiceovers/{slug}_vo.mp3"
        vo_path = generate_voiceover(script_data.get("full_script", ""), vo_out_path, provider="hume")
        vo_dur = get_voiceover_duration(vo_path)

        # Step 4: Music
        print("\n--- Step 4: Music Mixing ---")
        main_mood = get_mood_for_section("context")
        music_src = select_music(main_mood, vo_dur)
        mixed_path = apply_music_ducking(vo_path, music_src, f"output/voiceovers/{slug}_mixed.mp3")

        # Step 5: Remotion Data
        print("\n--- Step 5: Remotion Data File ---")
        remotion_data = _build_remotion_data(script_data, broll_dict, mixed_path, "", hook_text)
        data_out = f"output/remotion_data/{slug}.json"
        os.makedirs("output/remotion_data", exist_ok=True)
        with open(data_out, "w", encoding="utf-8") as f:
            json.dump(remotion_data, f, indent=2, ensure_ascii=False)

        # Step 6: Render
        print("\n--- Step 6: Video Render ---")
        video_out = f"output/videos/{slug}.mp4"
        os.makedirs("output/videos", exist_ok=True)
        _stream_render("VerticalShort", data_out, video_out)

        # Step 7: Upload
        print("\n--- Step 7: YouTube Upload ---")
        desc = f"Watch this short about {topic}! #shorts #news"
        if not dry_run:
            uploader = YouTubeUploader()
            yt_id = uploader.upload_video(video_out, topic, desc, ["shorts", "news"], category_id="25")
            print(f"Uploaded: {yt_id}")
        else:
            print("Dry run: Skipping upload")
            os.makedirs("output", exist_ok=True)
            dry_out = f"output/dry_run_upload_{slug}.json"
            with open(dry_out, "w", encoding="utf-8") as f:
                json.dump({
                    "file_path": video_out,
                    "title": topic,
                    "description": desc,
                    "tags": ["shorts", "news"]
                }, f, indent=2)
            
        print("Pipeline finished successfully.")

    except Exception as e:
        print(f"\n[!] Pipeline failed: {e}")
        raise e

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Shorts Pipeline")
    parser.add_argument("topic", help="Topic for the video")
    parser.add_argument("--dry-run", action="store_true", help="Skip actual YouTube upload")
    
    args = parser.parse_args()
    run_shorts_pipeline(args.topic, dry_run=args.dry_run)
