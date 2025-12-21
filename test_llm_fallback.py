import os
import asyncio
from processors.rewrite_breaking import ScriptRewriter
from dotenv import load_dotenv

load_dotenv()

async def test_fallback():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not found.")
        return

    rewriter = ScriptRewriter(api_key)
    
    print("\n--- Testing Keyword Generation Fallback ---")
    # This might trigger 429 based on recent test_gemini.py run
    sentence = "The global economy is facing a significant downturn according to the latest reports."
    keywords = rewriter.generate_image_keywords(sentence)
    print(f"Keywords: {keywords}")
    
    if "error" in keywords.lower() or "quota" in keywords.lower():
        print("FAILED: Error leakage detected in keywords!")
    else:
        print("SUCCESS: Keywords are clean (either actual AI keywords or static fallback).")

    print("\n--- Testing Script Generation Fallback ---")
    headline = "Global Summit Starts in Paris"
    content = "Leaders from around the world have gathered in Paris to discuss climate change and economic stability."
    script = rewriter.rewrite_for_shorts(headline, content)
    print(f"Script preview: {script[:100]}...")
    
    if "error" in script.lower() or "quota" in script.lower() or "maximum retries" in script.lower():
        print("FAILED: Error leakage detected in script!")
    else:
        print("SUCCESS: Script is clean.")

if __name__ == "__main__":
    asyncio.run(test_fallback())
