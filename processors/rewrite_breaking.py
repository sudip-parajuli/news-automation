import os
import re
import time
import random
from dotenv import load_dotenv
from scripts.llm_utils import call_gemini

load_dotenv()

class LLMGenerationError(Exception):
    """Custom exception for LLM generation failures."""
    pass

class ScriptRewriter:
    def __init__(self, api_key: str = None):
        # api_key kept for backwards-compat but ignored — GeminiKeyRotator handles rotation
        pass

    def _call_with_retry(self, prompt: str, max_retries: int = 5) -> str:
        """Calls Gemini via GeminiKeyRotator with automatic key rotation and Groq fallback."""
        # call_gemini internally handles rotation, cooldowns, and Groq fallback
        return call_gemini(
            system_prompt="You are a professional news script writer.",
            user_prompt=prompt,
        )

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
