import sys
from dotenv import load_dotenv
load_dotenv()
from scripts.longform_script_generator import LongformScriptGenerator

def main():
    topic = "Why oil prices are spiking globally"
    print(f"Running smoke test for topic: {topic}")
    
    try:
        generator = LongformScriptGenerator()
        result = generator.generate_script(topic)
        
        print("\n--- SMOKE TEST SUCCESS ---")
        print(f"Topic: {result['topic']}")
        print(f"Sections extracted: {list(result['sections'].keys())}")
        print(f"Best title option: {result['metadata']['title_options'][0]}") # just pick first for display
        
        full_script = result['full_script']
        word_count = len(full_script.split())
        print(f"Word Count: {word_count} words")
        
        if 1200 <= word_count <= 1800:
            print("Word count check: PASS (1,200 - 1,800 words)")
        elif word_count < 1200:
            print("Word count check: FAIL (Under 1,200 words)")
        else:
            print("Word count check: FAIL (Over 1,800 words)")
            
    except Exception as e:
        print(f"\n--- SMOKE TEST FAILED ---")
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
