import os
import shutil
import subprocess
import argparse
import base64
import json
from pathlib import Path

def print_result(name: str, passed: bool, details: str = ""):
    status = "[\033[92mPASS\033[0m]" if passed else "[\033[91mFAIL\033[0m]"
    print(f"{status} {name:30} {details}")

def check_binaries():
    print("\n--- Checking Binaries ---")
    binaries = ["ffmpeg", "ffprobe", "node"]
    all_passed = True
    for b in binaries:
        path = shutil.which(b)
        if path:
            print_result(b, True, f"Found at {path}")
        else:
            print_result(b, False, "Not found in PATH")
            all_passed = False
    return all_passed

def check_env_vars(skip_youtube_live: bool = False):
    print("\n--- Checking API Keys & Tokens ---")
    required = [
        "GEMINI_API_KEY",
        "PEXELS_API_KEY",
        "PIXABAY_API_KEY",
        "HUME_API_KEY",
        "HUME_API_KEY2",
        "HUME_API_KEY3",
        "HUME_API_KEY4",
        "HUME_API_KEY5",
        "HUME_VOICE_ID",
        "YOUTUBE_TOKEN_BASE64"
    ]
    all_passed = True
    for req in required:
        val = os.getenv(req)
        if val:
            if req == "YOUTUBE_TOKEN_BASE64":
                try:
                    token_data = base64.b64decode(val)
                    token_json = json.loads(token_data)
                    # For youtube uploader
                    if "refresh_token" in token_json or token_json.get("type") == "service_account":
                        print_result(req, True, "Set and valid JSON")
                    else:
                        print_result(req, False, "Decoded JSON missing refresh_token or type:service_account")
                        all_passed = False
                except Exception as e:
                    print_result(req, False, f"Failed to decode base64 or parse JSON: {e}")
                    all_passed = False
            else:
                print_result(req, True, "Set")
        else:
            print_result(req, False, "Not set in environment")
            all_passed = False
            
    if skip_youtube_live:
        print_result("YOUTUBE_LIVE_CHECK", True, "Skipped by --skip-youtube-live")
    # else: you'd do a live check here if needed
    
    return all_passed

def check_fonts():
    print("\n--- Checking Essential Fonts ---")
    fonts = ["Anton-Regular.ttf", "Montserrat-Bold.ttf"]
    font_dir = Path("assets/fonts")
    all_passed = True
    for f in fonts:
        p = font_dir / f
        if p.exists():
            print_result(f, True, "Found")
        else:
            print_result(f, False, f"Missing: {p}")
            all_passed = False
    return all_passed

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-youtube-live", action="store_true", help="Skip making live API call to YouTube")
    args = parser.parse_args()

    print("=" * 60)
    print("PREFLIGHT CHECKLIST")
    print("=" * 60)
    
    # Load env from .env if running locally
    from dotenv import load_dotenv
    load_dotenv()
    
    b_ok = check_binaries()
    e_ok = check_env_vars(args.skip_youtube_live)
    f_ok = check_fonts()
    
    print("\n" + "=" * 60)
    if b_ok and e_ok and f_ok:
        print("\033[92mALL CHECKS PASSED. SYSTEM IS READY FOR PRODUCTION.\033[0m")
    else:
        print("\033[91mPREFLIGHT FAILED. PLEASE FIX THE ISSUES ABOVE.\033[0m")
        exit(1)

if __name__ == "__main__":
    main()
