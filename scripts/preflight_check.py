import os
import shutil
import subprocess
import argparse
import base64
import json
import pickle
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
        "GEMINI_API_KEY2",
        "GEMINI_API_KEY3",
        "GEMINI_API_KEY4",
        "GROQ_API_KEY",
        "GROQ_API_KEY2",
        "GROQ_API_KEY3",
        "GROQ_API_KEY4",
        "PEXELS_API_KEY",
        "PIXABAY_API_KEY",
        "HUME_API_KEY",
        "HUME_API_KEY2",
        "HUME_API_KEY3",
        "HUME_API_KEY4",
        "HUME_API_KEY5",
        "HUME_API_KEY6",
        "HUME_API_KEY7",
        "HUME_API_KEY8",
        "HUME_API_KEY9",
        "HUME_API_KEY10",
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
                    creds = pickle.loads(token_data)
                    # For youtube uploader pickle
                    if hasattr(creds, 'refresh_token') or hasattr(creds, 'token') or hasattr(creds, '_service_account_email'):
                        print_result(req, True, "Set and valid pickle")
                    else:
                        print_result(req, False, "Decoded pickle missing credentials format")
                        all_passed = False
                except Exception as e:
                    print_result(req, False, f"Failed to decode base64 or parse pickle: {e}")
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

# Fonts are downloaded dynamically during the pipeline run,
# so we no longer block the preflight check on them.

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
    
    print("\n" + "=" * 60)
    if b_ok and e_ok:
        print("\033[92mALL CHECKS PASSED. SYSTEM IS READY FOR PRODUCTION.\033[0m")
    else:
        print("\033[91mPREFLIGHT FAILED. PLEASE FIX THE ISSUES ABOVE.\033[0m")
        exit(1)

if __name__ == "__main__":
    main()
