from google import genai
from google.genai import types
import os
import time
import random
from dotenv import load_dotenv

load_dotenv()

class LLMGenerationError(Exception):
    """Custom exception for LLM generation failures."""
    pass

class ScriptRewriter:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.model_name = 'gemini-2.0-flash'
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.groq_client = None
        if self.groq_api_key:
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=self.groq_api_key)
            except ImportError:
                print("Groq library not installed, fallback will not be available.")
        else:
            print("GROQ_API_KEY not found in .env, fallback will not be available.")

    def _call_with_retry(self, prompt: str, max_retries: int = 5) -> str:
        """Calls Gemini with exponential backoff, falling back to Groq if available."""
        last_error = ""
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
                if response and response.text:
                    return response.text.strip()
                raise LLMGenerationError("Empty response from Gemini")
            except Exception as e:
                err_msg = str(e)
                last_error = err_msg
                # Handle quota or service issues
                if "429" in err_msg or "ResourceExhausted" in err_msg or "503" in err_msg:
                    print(f"Gemini Issue: Quota or Service Unavailable. Attempt {attempt+1}/{max_retries}")
                    
                    # Immediate fallback to Groq if available
                    if self.groq_client:
                        print("Trying Groq fallback...")
                        try:
                            chat_completion = self.groq_client.chat.completions.create(
                                messages=[{"role": "user", "content": prompt}],
                                model="llama-3.3-70b-versatile",
                            )
                            content = chat_completion.choices[0].message.content.strip()
                            if content:
                                return content
                        except Exception as groq_err:
                            print(f"Groq fallback failed: {groq_err}")
                    
                    # Wait and retry Gemini
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    print(f"Retrying Gemini in {wait_time:.2f} seconds...")
                    time.sleep(wait_time)
                else:
                    print(f"Unexpected Gemini error: {err_msg}")
                    if attempt == max_retries - 1:
                        raise LLMGenerationError(f"Unexpected LLM error: {err_msg}")
                    time.sleep(2)
        
        raise LLMGenerationError(f"Maximum retries reached for LLM generation. Last error: {last_error}")

    def rewrite_for_shorts(self, headline: str, content: str) -> str:
        prompt = f"""
        Rewrite this international breaking news into a 25–40 second YouTube Shorts script.
        Headline: {headline}
        Content: {content}

        Language: English
        Tone: Urgent, neutral, factual
        - RETURN ONLY THE SPEECH TEXT. 
        - DO NOT include narrator instructions like "[Music plays]".
        - DO NOT include speaker labels like "Anchor:".
        - DO NOT include hashtags.
        Simple global English
        End with: 'More updates will follow.'
        """
        try:
            script = self._call_with_retry(prompt)
            return self.clean_script(script)
        except LLMGenerationError as e:
            print(f"Hard fallback for script generation: {e}")
            return f"{headline}. {content[:150]}. More updates will follow."

    def clean_script(self, text: str) -> str:
        """Removes common narrator patterns like [Music] or Anchor: from text."""
        import re
        # Remove patterns like [Music plays], [Serious music], (Upbeat tone)
        text = re.sub(r'\[.*?\]', '', text)
        text = re.sub(r'\(.*?\)', '', text)
        # Remove speaker labels like Anchor:, Narrator:, Voiceover:
        text = re.sub(r'^(Anchor|Narrator|Voiceover|Anchorperson):\s*', '', text, flags=re.IGNORECASE | re.MULTILINE)
        # Remove hashtags
        text = re.sub(r'#\w+', '', text)
        return text.strip()

    def summarize_for_daily(self, news_items: list) -> str:
        news_text = "\n\n".join([f"Headline: {item['headline']}\nContent: {item['content']}" for item in news_items])
        prompt = f"""
        Summarize today’s major international news into a 6–8 minute YouTube video script.
        
        News items:
        {news_text}

        Language: English
        Tone: Professional news anchor
        Group related stories
        Use clear transitions between topics
        Avoid repetition or bias
        - RETURN ONLY THE SPEECH TEXT.
        - DO NOT include labels like "Segment 1" or "Visual:".
        """
        try:
            script = self._call_with_retry(prompt)
            return self.clean_script(script)
        except LLMGenerationError as e:
            print(f"Hard fallback for script generation: {e}")
            return " ".join([f"{item['headline']}." for item in news_items])

    def generate_image_keywords(self, sentence: str) -> str:
        """
        Generates 3-5 descriptive keywords for an image search based on the sentence.
        Aims for 'news-worthy' photographic subjects.
        """
        prompt = f"""
        Extract 3-5 highly descriptive keywords for a news photographic image search from this sentence:
        "{sentence}"
        
        Rules:
        - Focus on real-world objects, people, or locations.
        - AVOID generic words like "system", "process", "decision", "random".
        - AVOID abstract concepts or diagrams.
        - Output ONLY the keywords separated by spaces.
        - Example: "US government discontinues lottery" -> "US Capitol Building Immigration"
        """
        
        try:
            keywords = self._call_with_retry(prompt)
            # Ensure keywords don't contain error messages
            if "error" in keywords.lower() or "limit reached" in keywords.lower() or "quota" in keywords.lower():
                 raise LLMGenerationError("Invalid keywords generated (leakage detected)")

            # Clean up formatting
            return " ".join(keywords.replace('"', '').replace(',', ' ').split())
        except Exception as e:
            print(f"Image keyword generation failed, using simple fallback: {e}")
            # Fallback to simple extraction: take nouns/longer words
            words = [w for w in sentence.split() if len(w) > 4 and w.lower() not in ['this', 'that', 'there', 'their', 'about']]
            return " ".join(words[:4])

if __name__ == "__main__":
    API_KEY = os.getenv("GEMINI_API_KEY")
    if API_KEY:
        rewriter = ScriptRewriter(API_KEY)
    else:
        print("GEMINI_API_KEY not found.")
