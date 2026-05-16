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

# Load env before any imports
load_dotenv()

from scripts.longform_script_generator import LongformScriptGenerator
from scripts.broll_fetcher import BRollFetcher
from scripts.voiceover_generator import generate_voiceover, get_voiceover_duration, estimate_word_timestamps, build_ssml, SECTION_WPM, DEFAULT_WPM
from scripts.music_selector import select_music, apply_music_ducking, get_mood_for_section
from scripts.thumbnail_generator import generate_longform_thumbnail, select_best_thumbnail, download_fonts
from uploader.youtube_uploader import YouTubeUploader


def _make_slug(topic: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', topic.lower()).strip('_')

def _generate_chapters(script_data: dict) -> str:
    chapters = []
    cursor = 0.0
    sections = script_data.get("sections", {})
    
    # Always start with 00:00
    chapters.append("00:00 - Introduction")
    
    section_order = ["hook", "context", "conflict", "evidence", "twist", "resolution", "cta"]
    
    for i, section_id in enumerate(section_order):
        text = sections.get(section_id, "").strip()
        if not text:
            continue
            
        word_count = len(text.split())
        wpm = SECTION_WPM.get(section_id, DEFAULT_WPM)
        duration_sec = (word_count / wpm) * 60.0
        
        cursor += duration_sec
        
        # Look ahead for the next section to label the timestamp
        next_section = None
        for next_id in section_order[i+1:]:
            if sections.get(next_id, "").strip():
                next_section = next_id
                break
                
        if next_section:
            chapter_title = next_section.title()
            if next_section == "cta":
                chapter_title = "Conclusion"
            
            m = int(cursor // 60)
            s = int(cursor % 60)
            chapters.append(f"{m:02d}:{s:02d} - {chapter_title}")
            
    return "\n".join(chapters)


def _save_state(state: dict):
    path = f"output/pipeline_state/{state['slug']}.json"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def _load_state(slug: str) -> dict:
    path = f"output/pipeline_state/{slug}.json"
    if not os.path.exists(path):
        raise FileNotFoundError(f"State file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _assemble_description(resolution_text: str, search_keywords: list, topic: str, chapters: str = "") -> str:
    sentences = re.split(r'(?<=[.!?])\s+', resolution_text.strip())
    first_two = " ".join(sentences[:2]).strip()
    
    desc = f"{first_two}\n\nWatch till the end for the twist.\n\n"
    if chapters:
        desc += f"Chapters:\n{chapters}\n\n"
        
    desc += f"Topics covered: {' | '.join(search_keywords)}\n\n"
    
    slug_keywords = [k for k in _make_slug(topic).split('_') if len(k) > 3]
    tags = ["news", "explained"] + slug_keywords[:2]
    desc += " ".join([f"#{t}" for t in tags])
    
    return desc


def _build_remotion_data(script_data: dict, broll_dict: dict, voiceover_path: str, music_path: str, title: str) -> dict:
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
                
            # Rename duration_seconds to duration for Remotion TypeScript interface
            if "duration_seconds" in b_copy:
                b_copy["duration"] = b_copy.pop("duration_seconds")
                
            abs_broll.append(b_copy)
            
        sections.append({
            "id": section_id,
            "text": text,
            "broll": abs_broll
        })
        
    abs_vo = os.path.abspath(voiceover_path) if voiceover_path and not os.path.isabs(voiceover_path) else voiceover_path
    abs_music = os.path.abspath(music_path) if music_path and not os.path.isabs(music_path) else music_path
        
    return {
        "title": title,
        "sections": sections,
        "voiceover_file": abs_vo,
        "background_music": abs_music
    }


def _stream_render(composition: str, data_path: str, output_path: str):
    node_path = shutil.which("node")
    if not node_path:
        raise RuntimeError("node not found in PATH. Install Node.js to enable Remotion rendering.")
        
    print(f"Checking Remotion bundle cache...")
    
    # Check if we need to rebundle
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
        print(f"Warning: Rebundle check failed ({e}), forcing rebundle.")
        
    if needs_rebundle:
        print("Rebundling Remotion application...")
        bundle_cmd = [node_path, "remotion/bundle.mjs"]
        b_proc = subprocess.Popen(bundle_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        
        for line in b_proc.stdout:
            print(f"  [Bundler] {line.strip()}")
            if line.startswith("BUNDLE_PATH:"):
                bundle_path = line.replace("BUNDLE_PATH:", "").strip()
        
        b_proc.wait()
        if b_proc.returncode != 0 or not bundle_path:
            raise RuntimeError(f"Remotion bundler failed with exit code {b_proc.returncode}")
            
        os.makedirs(os.path.dirname(bundle_path_file), exist_ok=True)
        with open(bundle_path_file, "w", encoding="utf-8") as f:
            f.write(bundle_path)
    else:
        print(f"Using cached Remotion bundle: {bundle_path}")
        
    print(f"Syncing assets to Remotion bundle directory ({bundle_path})...")
    # Copy all necessary assets to the bundle directory so Remotion's HTTP server can serve them natively
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

    # Note: We must also update the data JSON to use relative paths so they resolve against the bundle HTTP server
    with open(data_path, "r", encoding="utf-8") as f:
        remotion_data = json.load(f)
        
    # Rewrite paths to be relative to the bundle root
    for section in remotion_data.get("sections", []):
        for b in section.get("broll", []):
            fname = os.path.basename(b["file_path"])
            b["file_path"] = f"{fname}" # In utils.ts, we need to make sure this resolves, but wait, we copied to bundle_path/broll_cache
            b["file_path"] = f"broll_cache/{fname}"
            
    vo_path = remotion_data.get("voiceover_file", "")
    if vo_path:
        remotion_data["voiceover_file"] = f"voiceovers/{os.path.basename(vo_path)}"
        
    music_path = remotion_data.get("background_music", "")
    if music_path:
        remotion_data["background_music"] = f"music/{os.path.basename(music_path)}"
        
    # Write back the updated data path
    updated_data_path = data_path.replace(".json", "_relative.json")
    with open(updated_data_path, "w", encoding="utf-8") as f:
        json.dump(remotion_data, f, indent=2)
        
    print(f"Starting Remotion render to {output_path}...")
    
    # Ensure dir exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # render.mjs expects: node render.mjs --composition <id> --data <path> --output <path> --bundle <path>
    cmd = [
        node_path, 
        "remotion/render.mjs", 
        "--composition", composition,
        "--data", updated_data_path,
        "--output", output_path,
        "--bundle", bundle_path
    ]
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    for line in process.stdout:
        print(f"  [Remotion] {line.strip()}")
        
    process.wait()
    if process.returncode != 0:
        raise RuntimeError(f"Remotion render failed with exit code {process.returncode}")
        
    if not os.path.exists(output_path):
        raise RuntimeError("Remotion render failed: Output file not created")
        
    video_size = os.path.getsize(output_path)
    if video_size < 1_000_000:
        # Since we use real renderer now, anything <1MB is likely a silent failure (e.g., blank frames)
        print(f"Warning: Render output is suspiciously small ({video_size} bytes).")


def check_file_exists(step: int, field: str, path: str):
    if not path or not os.path.exists(path):
        raise FileNotFoundError(f"Cannot resume: {field} from step {step} no longer exists at {path}")


def run_pipeline(topic: str, dry_run: bool = False, slug: str = None, from_step: int = 1):
    print(f"=== Starting Long-Form Pipeline {'(DRY RUN)' if dry_run else ''} ===")
    print(f"Topic: {topic}")
    
    if not slug:
        slug = _make_slug(topic) + f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
    print(f"Slug: {slug}")
    print(f"Starting from step: {from_step}\n")
    
    # Initialize state
    if from_step == 1:
        state = {
            "topic": topic,
            "slug": slug,
            "status": "in_progress",
            "completed_steps": [],
            "failed_step": None,
            "step_outputs": {}
        }
        _save_state(state)
    else:
        state = _load_state(slug)
        state["status"] = "in_progress"
        state["failed_step"] = None
        _save_state(state)
        
        # Validate past step outputs exist on disk
        print("Validating outputs from previous steps...")
        if from_step > 1:
            so = state.get("step_outputs", {})
            if "1" not in so: raise ValueError("Cannot resume: Step 1 output missing from state")
            check_file_exists(1, "script_path", so["1"].get("script_path"))
            
        if from_step > 2:
            so = state.get("step_outputs", {})
            if "2" not in so: raise ValueError("Cannot resume: Step 2 output missing from state")
            # Can't easily check all broll paths, assume ok if key exists
            if not so["2"].get("broll"): raise ValueError("Cannot resume: broll data empty")
            
        if from_step > 3:
            so = state.get("step_outputs", {})
            if "3" not in so: raise ValueError("Cannot resume: Step 3 output missing from state")
            check_file_exists(3, "voiceover_path", so["3"].get("voiceover_path"))
            
        if from_step > 4:
            so = state.get("step_outputs", {})
            if "4" not in so: raise ValueError("Cannot resume: Step 4 output missing from state")
            check_file_exists(4, "music_path", so["4"].get("music_path"))
            
        if from_step > 5:
            so = state.get("step_outputs", {})
            if "5" not in so: raise ValueError("Cannot resume: Step 5 output missing from state")
            check_file_exists(5, "thumbnail_path", so["5"].get("thumbnail_path"))
            
        if from_step > 6:
            so = state.get("step_outputs", {})
            if "6" not in so: raise ValueError("Cannot resume: Step 6 output missing from state")
            check_file_exists(6, "remotion_data_path", so["6"].get("remotion_data_path"))
            
        if from_step > 7:
            so = state.get("step_outputs", {})
            if "7" not in so: raise ValueError("Cannot resume: Step 7 output missing from state")
            check_file_exists(7, "video_path", so["7"].get("video_path"))
            
        print("Validation passed. Resuming...\n")
        
    summary = {}
    
    try:
        # Step 1: Script Generation
        if from_step <= 1:
            print("--- Step 1: Script Generation ---")
            script_gen = LongformScriptGenerator()
            script_data = script_gen.generate_script(topic)
            
            # Find the saved json path
            script_matches = sorted(glob.glob(f"output/scripts/{_make_slug(topic)}*.json"))
            script_path = script_matches[-1] if script_matches else None
            
            word_count = len(script_data.get("full_script", "").split())
            
            state["step_outputs"]["1"] = {"script_path": script_path, "word_count": word_count}
            state["completed_steps"].append(1)
            _save_state(state)
            summary[1] = ("Script generation", "PASS", f"{word_count} words")
        else:
            with open(state["step_outputs"]["1"]["script_path"], "r", encoding="utf-8") as f:
                script_data = json.load(f)
            summary[1] = ("Script generation", "SKIP", f"{state['step_outputs']['1'].get('word_count', '?')} words")

        # Step 2: B-Roll Fetch
        if from_step <= 2:
            print("\n--- Step 2: B-Roll Fetch ---")
            fetcher = BRollFetcher()
            sections = script_data.get("sections", {})
            broll_dict = fetcher.fetch_broll_for_script(sections)
            
            clip_count = sum(len(clips) for clips in broll_dict.values())
            vid_count = sum(1 for clips in broll_dict.values() for c in clips if c.get("type") == "video")
            img_count = sum(1 for clips in broll_dict.values() for c in clips if c.get("type") == "still_image")
            
            state["step_outputs"]["2"] = {"broll": broll_dict}
            state["completed_steps"].append(2)
            _save_state(state)
            summary[2] = ("B-roll fetch", "PASS", f"{clip_count} clips ({vid_count} video, {img_count} still)")
        else:
            broll_dict = state["step_outputs"]["2"]["broll"]
            summary[2] = ("B-roll fetch", "SKIP", "loaded from state")

        # Step 3: Voiceover Generation
        if from_step <= 3:
            print("\n--- Step 3: Voiceover ---")
            # Build SSML instead of raw text
            ssml_text = build_ssml(script_data.get("sections", {}))
            vo_out_path = f"output/voiceovers/{slug}_vo.mp3"
            os.makedirs("output/voiceovers", exist_ok=True)
            
            # Since generate_voiceover takes raw text and _call_google_tts takes SSML natively,
            # wait, Phase 7 implemented generate_voiceover_from_ssml
            from scripts.voiceover_generator import generate_voiceover_from_ssml
            try:
                vo_path = generate_voiceover_from_ssml(ssml_text, vo_out_path)
            except Exception as e:
                print(f"generate_voiceover_from_ssml failed: {e}. Falling back to generate_voiceover with text...")
                try:
                    vo_path = generate_voiceover(script_data.get("full_script", ""), vo_out_path, provider="auto")
                except Exception as inner_e:
                    if dry_run:
                        print(f"Voiceover generation failed: {inner_e}. Using 30s silence for DRY RUN.")
                        subprocess.run([
                            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                            "-t", "30", "-q:a", "9", "-acodec", "libmp3lame", vo_out_path
                        ], check=True, capture_output=True)
                        vo_path = vo_out_path
                    else:
                        raise inner_e
                
            vo_dur = get_voiceover_duration(vo_path)
            
            state["step_outputs"]["3"] = {"voiceover_path": vo_path, "duration_seconds": vo_dur}
            state["completed_steps"].append(3)
            _save_state(state)
            summary[3] = ("Voiceover", "PASS", f"{vo_dur/60:.1f} min")
        else:
            vo_path = state["step_outputs"]["3"]["voiceover_path"]
            vo_dur = state["step_outputs"]["3"]["duration_seconds"]
            summary[3] = ("Voiceover", "SKIP", f"{vo_dur/60:.1f} min")

        # Step 4: Music Mixing
        if from_step <= 4:
            print("\n--- Step 4: Music Mixing ---")
            main_mood = get_mood_for_section("context")
            music_src = select_music(main_mood, vo_dur)

            if music_src:
                mixed_out = f"output/voiceovers/{slug}_mixed.mp3"
                mixed_path = apply_music_ducking(vo_path, music_src, mixed_out)
                summary[4] = ("Music mixing", "PASS", f"mixed with {os.path.basename(music_src)}")
            else:
                # No local music and Pixabay unavailable — use raw voiceover
                mixed_path = vo_path
                print("WARNING: No music available — using voiceover-only audio")
                summary[4] = ("Music mixing", "SKIP", "no music available, using VO only")

            state["step_outputs"]["4"] = {"music_path": mixed_path}
            state["completed_steps"].append(4)
            _save_state(state)
        else:
            mixed_path = state["step_outputs"]["4"]["music_path"]
            summary[4] = ("Music mixing", "SKIP", "loaded from state")

        # Step 5: Thumbnails
        if from_step <= 5:
            print("\n--- Step 5: Thumbnails ---")
            os.makedirs("output/thumbnails", exist_ok=True)
            download_fonts()
            
            title_opts = script_data.get("metadata", {}).get("title_options", [])
            keywords = script_data.get("metadata", {}).get("thumbnail_keywords", [])
            
            if len(title_opts) >= 2:
                title_a = title_opts[0]
                title_b = title_opts[1]
                path_a = f"output/thumbnails/{slug}_a.png"
                path_b = f"output/thumbnails/{slug}_b.png"
                
                generate_longform_thumbnail(title_a, topic, keywords, path_a)
                generate_longform_thumbnail(title_b, topic, keywords, path_b)
                
                winning_title, _ = select_best_thumbnail(title_a, title_b, topic)
                final_thumb = path_a if winning_title == title_a else path_b
            else:
                winning_title = title_opts[0] if title_opts else topic
                final_thumb = f"output/thumbnails/{slug}.png"
                generate_longform_thumbnail(winning_title, topic, keywords, final_thumb)
                
            state["step_outputs"]["5"] = {"thumbnail_path": final_thumb, "winning_title": winning_title}
            state["completed_steps"].append(5)
            _save_state(state)
            summary[5] = ("Thumbnails", "PASS", winning_title[:30] + "...")
        else:
            final_thumb = state["step_outputs"]["5"]["thumbnail_path"]
            winning_title = state["step_outputs"]["5"]["winning_title"]
            summary[5] = ("Thumbnails", "SKIP", "loaded from state")

        # Step 6: Remotion Data File
        if from_step <= 6:
            print("\n--- Step 6: Remotion Data File ---")
            remotion_data = _build_remotion_data(script_data, broll_dict, mixed_path, "", winning_title)
            
            data_out = f"output/remotion_data/{slug}.json"
            os.makedirs("output/remotion_data", exist_ok=True)
            with open(data_out, "w", encoding="utf-8") as f:
                json.dump(remotion_data, f, indent=2, ensure_ascii=False)
                
            state["step_outputs"]["6"] = {"remotion_data_path": data_out}
            state["completed_steps"].append(6)
            _save_state(state)
            summary[6] = ("Remotion data file", "PASS", data_out)
        else:
            data_out = state["step_outputs"]["6"]["remotion_data_path"]
            summary[6] = ("Remotion data file", "SKIP", "loaded from state")

        # Step 7: Video Render
        if from_step <= 7:
            print("\n--- Step 7: Video Render ---")
            video_out = f"output/videos/{slug}.mp4"
            
            try:
                _stream_render("LongFormExplainer", data_out, video_out)
                vsize = os.path.getsize(video_out)
                state["step_outputs"]["7"] = {"video_path": video_out}
                state["completed_steps"].append(7)
                _save_state(state)
                summary[7] = ("Video render", "PASS", f"{vsize / 1_000_000:.1f} MB")
            except ValueError as e:
                if "STUB_RENDER" in str(e):
                    # We expect this for now
                    print(f"Notice: {e}")
                    state["step_outputs"]["7"] = {"video_path": video_out}
                    state["completed_steps"].append(7)
                    _save_state(state)
                    vsize = os.path.getsize(video_out) if os.path.exists(video_out) else 0
                    summary[7] = ("Video render", "PASS (stub)", f"{vsize} bytes")
                else:
                    raise e
        else:
            video_out = state["step_outputs"]["7"]["video_path"]
            summary[7] = ("Video render", "SKIP", "loaded from state")

        # Step 8: Upload
        if from_step <= 8:
            print("\n--- Step 8: YouTube Upload ---")
            resolution_text = script_data.get("sections", {}).get("resolution", "")
            search_kws = script_data.get("metadata", {}).get("search_keywords", [])
            chapters_text = _generate_chapters(script_data)
            desc = _assemble_description(resolution_text, search_kws, topic, chapters_text)
            
            if dry_run:
                payload = {
                    "file_path": video_out,
                    "title": winning_title,
                    "description": desc,
                    "tags": search_kws,
                    "category_id": "25",
                    "thumbnail_path": final_thumb
                }
                dry_out = f"output/dry_run_upload_{slug}.json"
                os.makedirs("output", exist_ok=True)
                with open(dry_out, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2, ensure_ascii=False)
                
                state["step_outputs"]["8"] = {"youtube_id": f"dry_run_{slug}"}
                state["completed_steps"].append(8)
                _save_state(state)
                summary[8] = ("Upload (DRY RUN)", "PASS", dry_out)
            else:
                if not os.path.exists("client_secrets.json"):
                    print(f"UPLOAD SKIPPED: client_secrets.json not found. Video saved at {video_out}")
                    summary[8] = ("YouTube Upload", "SKIP", "client_secrets.json missing")
                else:
                    uploader = YouTubeUploader()
                    yt_id = uploader.upload_video(
                        file_path=video_out,
                        title=winning_title,
                        description=desc,
                        tags=search_kws,
                        category_id="25"
                    )
                    state["step_outputs"]["8"] = {"youtube_id": yt_id}
                    state["completed_steps"].append(8)
                    _save_state(state)
                    summary[8] = ("YouTube Upload", "PASS", f"ID: {yt_id}")
        
        state["status"] = "completed"
        _save_state(state)
        
        print("\n" + "="*60)
        print("PIPELINE SUMMARY")
        print("="*60)
        print(f"{'Step':<5} | {'Description':<20} | {'Status':<12} | {'Output'}")
        print("-" * 60)
        for i in range(1, 9):
            if i in summary:
                desc, status, out = summary[i]
                print(f"{i:<5} | {desc:<20} | {status:<12} | {out}")
        print("="*60)

    except Exception as e:
        print(f"\n[!] Pipeline failed at step {from_step}: {e}")
        state["status"] = "failed"
        state["failed_step"] = from_step
        _save_state(state)
        raise e


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Long-Form Explainer Pipeline")
    parser.add_argument("topic", help="Topic for the video")
    parser.add_argument("--dry-run", action="store_true", help="Skip actual YouTube upload")
    parser.add_argument("--slug", help="Resume specific pipeline slug")
    parser.add_argument("--from-step", type=int, default=1, help="Step to resume from (1-8)")
    
    args = parser.parse_args()
    
    # We need glob for step 1 path finding
    import glob
    
    run_pipeline(args.topic, dry_run=args.dry_run, slug=args.slug, from_step=args.from_step)

