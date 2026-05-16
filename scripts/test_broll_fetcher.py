import os
from dotenv import load_dotenv
load_dotenv()

from scripts.broll_fetcher import BRollFetcher

def main():
    fetcher = BRollFetcher()
    
    sentence = "OPEC ministers met in Vienna to discuss production cuts amid falling crude prices"
    print(f"Testing single sentence fetch:\nSentence: {sentence}")
    
    try:
        broll = fetcher.fetch_broll(sentence)
        print("\nSingle Fetch Result:")
        print(f"Query used: {broll['query']}")
        print(f"File type:  {broll['type']}")
        print(f"File path:  {broll['file_path']}")
        print(f"Duration:   {broll['duration']}s")
    except Exception as e:
        print(f"Failed to fetch single broll: {e}")

    # Test fetch_broll_for_script
    print("\n\nTesting fetch_broll_for_script...")
    mock_sections = {
        "hook": "The world runs on oil, but the pumps might soon run dry.",
        "context": "OPEC ministers met in Vienna to discuss production cuts amid falling crude prices.",
        "conflict": "But the market reacted unpredictably, sending stock prices tumbling."
    }
    
    results = fetcher.fetch_broll_for_script(mock_sections)
    
    video_count = 0
    still_count = 0
    total_count = 0
    
    print("\nScript Fetch Results:")
    for section, brolls in results.items():
        print(f"\n[{section.upper()}]")
        for b in brolls:
            total_count += 1
            if b['type'] == 'video':
                video_count += 1
            else:
                still_count += 1
            print(f"  - Query: {b['query']} | Type: {b['type']} | Path: {b['file_path']} | Duration: {b['duration']}s")

    print("\n--- SUMMARY ---")
    print(f"{video_count}/{total_count} clips are video, {still_count}/{total_count} are still images")

if __name__ == "__main__":
    main()
