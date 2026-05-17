import sys
import os
from dotenv import load_dotenv
load_dotenv()
import scripts.llm_utils
from scripts.longform_script_generator import LongformScriptGenerator
from scripts.broll_fetcher import BRollFetcher

def main():
    topic = "Why oil prices are spiking globally"
    print(f"Running smoke test for topic: {topic}")
    
    # Patch call_gemini to count calls
    original_call_gemini = scripts.llm_utils.call_gemini
    call_count = 0
    def counted_call_gemini(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return original_call_gemini(*args, **kwargs)
    scripts.llm_utils.call_gemini = counted_call_gemini
    
    # Must also patch LongformScriptGenerator and BRollFetcher modules which may have imported it directly
    import scripts.longform_script_generator as lsg
    lsg.call_gemini = counted_call_gemini
    import scripts.broll_fetcher as bf
    bf.call_gemini = counted_call_gemini
    
    try:
        # Step 1: Script Generation
        print("Testing Script Generation...")
        generator = LongformScriptGenerator()
        result = generator.generate_script(topic)
        
        print("\n--- SMOKE TEST SUCCESS ---")
        print(f"Topic: {result['topic']}")
        print(f"Sections extracted: {list(result['sections'].keys())}")
        
        best_idx = result['metadata'].get('best_title_index', 0)
        titles = result['metadata'].get('title_options', [''])
        best_title = titles[best_idx] if best_idx < len(titles) else titles[0]
        
        print(f"Best title option (from metadata): {best_title}")
        print(f"Title reasoning: {result['metadata'].get('best_title_reasoning')}")
        
        full_script = result['full_script']
        word_count = len(full_script.split())
        print(f"Word Count: {word_count} words")
        
        # Step 2: B-Roll Batched Query Extraction
        print("\nTesting Batched B-Roll Query Extraction...")
        fetcher = BRollFetcher()
        batched_queries = fetcher._extract_all_keywords(result['sections'])
        print("Batched queries:", batched_queries)
        
        # Step 3: Thumbnail (Skipped as title selection is now in script generation)
        print("\nTesting Thumbnail (Title Selection is now batched!)")
        
        print(f"\nTotal LLM Call Count: {call_count}")
        if call_count <= 3:
            print("LLM call count optimization: PASS")
        else:
            print("LLM call count optimization: FAIL")
            
    except Exception as e:
        print(f"\n--- SMOKE TEST FAILED ---")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
