import os
from scripts.music_selector import select_music

if __name__ == "__main__":
    try:
        print("Testing Pixabay download...")
        audio_path = select_music("suspense", duration_seconds=60)
        print(f"Success! Music downloaded to {audio_path}")
        if os.path.exists(audio_path):
            size = os.path.getsize(audio_path)
            print(f"File size: {size} bytes")
    except Exception as e:
        print(f"Failed: {e}")
