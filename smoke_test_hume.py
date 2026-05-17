import os
import sys
import base64
import httpx
from unittest.mock import patch

# Inject fake keys for the test
os.environ["HUME_API_KEY"] = "fake_key_1"
os.environ["HUME_API_KEY2"] = "fake_key_2"
os.environ["HUME_API_KEY3"] = "fake_key_3"
os.environ["HUME_API_KEY4"] = "fake_key_4"
os.environ["HUME_API_KEY5"] = "fake_key_5"
os.environ["HUME_API_KEY6"] = "fake_key_6"
os.environ["HUME_API_KEY7"] = "fake_key_7"
os.environ["HUME_API_KEY8"] = "fake_key_8"
os.environ["HUME_API_KEY9"] = "fake_key_9"
os.environ["HUME_API_KEY10"] = "fake_key_10"
os.environ["HUME_VOICE_ID"] = "fake_voice_id"

# Now import the module so it picks up the keys
from scripts.voiceover_generator import generate_voiceover, get_voiceover_duration
import scripts.voiceover_generator as vg

def patched_split_into_chunks(text: str, max_chars: int = 100) -> list[str]:
    # Custom splitter to force small chunks for rotation test
    sentences = text.split(". ")
    chunks = []
    for s in sentences:
        if s:
            chunks.append(s.strip() + ".")
    return chunks

vg._split_into_chunks = patched_split_into_chunks

# Mock httpx.post to simulate API responses and a 429
call_count = {"fake_key_1": 0}

def mock_httpx_post(url, json=None, headers=None, timeout=None):
    key = headers.get("X-Hume-Api-Key")
    
    # Simulate a rate limit on the first key after 1 call
    if key == "fake_key_1":
        call_count["fake_key_1"] += 1
        if call_count["fake_key_1"] > 1:
            class Mock429:
                status_code = 429
            return Mock429()
            
    # Success response
    class MockSuccess:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            # 1 second of silent mp3 base64 encoded
            silent_mp3 = b'ID3\x04\x00\x00\x00\x00\x00\x00\xff\xfb\x90D\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            return {"generations": [{"audio": base64.b64encode(silent_mp3).decode()}]}
    return MockSuccess()

def main():
    test_text = "This is the first sentence of our Hume TTS smoke test. And this is the second sentence, which should trigger another API call. Finally, here is the third sentence to ensure our key rotation correctly cycles through the configured keys. This fourth sentence will trigger the rotation."
    output_path = "output/smoke_test_hume.mp3"
    
    print("Testing Hume TTS generation with key rotation...")
    
    try:
        with patch('httpx.post', side_effect=mock_httpx_post):
            final_path = generate_voiceover(test_text, output_path, provider="hume")
            
        print("\n--- SMOKE TEST SUCCESS ---")
        size_bytes = os.path.getsize(final_path)
        print(f"File created at: {final_path}")
        print(f"Size: {size_bytes} bytes")
        
        if size_bytes > 0:
            print("Hume TTS check: PASS")
        else:
            print("Hume TTS check: FAIL (Invalid size or duration)")
            
    except Exception as e:
        print(f"\n--- SMOKE TEST FAILED ---")
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
