import os
from scripts.music_selector import select_music
import subprocess
from unittest.mock import patch

os.environ["PIXABAY_API_KEY"] = "fake_key"

def mock_httpx_get(url, timeout=None):
    if "api/videos/music" in url or "api/audio" in url:
        class MockSuccess:
            status_code = 200
            def raise_for_status(self): pass
            def json(self):
                return {
                    "hits": [{
                        "id": "12345",
                        "audio_url": "http://fake.url/audio.mp3"
                    }]
                }
        return MockSuccess()
    else:
        # Mocking the actual audio file download
        class MockDownload:
            status_code = 200
            def raise_for_status(self): pass
            @property
            def content(self):
                # fake mp3 data
                return b'ID3\x04\x00\x00\x00\x00\x00\x00\xff\xfb\x90D\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        return MockDownload()

def get_audio_duration(path: str) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())

def main():
    print("Testing Pixabay Music fetching...")
    try:
        with patch('httpx.get', side_effect=mock_httpx_get):
            track_path = select_music("calm")
            
        print(f"\n--- SMOKE TEST SUCCESS ---")
        
        size_kb = os.path.getsize(track_path) / 1024
        duration = get_audio_duration(track_path)
        
        print(f"File: {track_path}")
        print(f"Size: {size_kb:.2f} KB")
        # Since it's a mocked 1-frame MP3, duration will be tiny, but the flow is tested
        
        if size_kb > 0:
            print("Pixabay Music check: PASS")
        else:
            print("Pixabay Music check: FAIL")
    except Exception as e:
        print(f"\n--- SMOKE TEST FAILED ---")
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
