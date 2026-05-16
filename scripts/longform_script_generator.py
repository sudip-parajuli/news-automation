import os
import json
import re
from datetime import datetime
from google import genai
import groq
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

REQUIRED_SECTIONS = [
    "[HOOK]", "[CONTEXT]", "[CONFLICT]", "[EVIDENCE]", 
    "[TWIST]", "[RESOLUTION]", "[CTA]"
]

class LLMGenerationError(Exception):
    pass

def llm_retry_decorator():
    return retry(
        wait=wait_exponential(min=2, max=30),
        stop=stop_after_attempt(4),
        reraise=True,
        retry=retry_if_exception_type((Exception,))
    )

class LongformScriptGenerator:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.client = None
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        self.model_name = 'gemini-2.0-flash'
        
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.groq_client = None
        if self.groq_api_key:
            self.groq_client = groq.Groq(api_key=self.groq_api_key)
        self.groq_model_name = 'llama-3.3-70b-versatile'
        
        if not self.client and not self.groq_client:
            raise ValueError("Either GEMINI_API_KEY or GROQ_API_KEY is required")

    @llm_retry_decorator()
    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        try:
            if not self.client:
                raise ValueError("Gemini client not initialized")
            from google import genai
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[system_prompt, user_prompt],
                config=genai.types.GenerateContentConfig(max_output_tokens=4096)
            )
            if not response or not response.text:
                raise ValueError("Empty response from Gemini")
            return response.text
        except Exception as e:
            print(f"Gemini generation failed: {e}. Attempting Groq fallback...")
            if not self.groq_client:
                raise e
            
            completion = self.groq_client.chat.completions.create(
                model=self.groq_model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=4096
            )
            if not completion or not completion.choices:
                raise ValueError("Empty response from Groq")
            return completion.choices[0].message.content

    def generate_script(self, topic: str) -> dict:
        system_prompt = """
        You are a senior documentary scriptwriter for a YouTube explainer channel.
        Your scripts are structured like mini-documentaries: they open with a mystery
        or surprising fact, build tension through context, deliver a twist or reveal
        in the middle, and close with a satisfying resolution plus a strong call to
        action. Your tone is authoritative but conversational — like a trusted friend
        who happens to know everything about the topic. Never use bullet points or
        numbered lists in the script. Write in flowing prose that sounds natural when
        spoken aloud.
        Every section MUST meet its minimum word count. Do not summarize or abbreviate.
        Write in full sentences. If a section feels complete, add a specific real-world
        example or data point to reach the minimum.
        """
        user_prompt = f"""
        Write a YouTube explainer script on this topic: {topic}

        Structure the script in exactly these labelled sections. You MUST meet the strict word count requirements for each section to reach a total of ~1,500 words.
        
        [HOOK] - (Strictly 100-150 words). Open with a single stunning fact, statistic, or
        question that makes the viewer need to know more. End with "And in this video,
        I'm going to show you exactly why." Never start with "In today's video."
        
        [CONTEXT] - (Strictly 300-350 words). Give the essential, deep background. What was the 
        situation before this happened? Who are the main players? Explain the history in rich detail.
        
        [CONFLICT] - (Strictly 350-400 words). What changed? What is the central tension or 
        problem? Use a specific event or moment as the turning point. Expand on the stakes and human impact.
        
        [EVIDENCE] - (Strictly 400-450 words). Back up the conflict with 3-4 specific facts,
        quotes, or data points. Dive deep into the analysis of each data point. Explain *how* we know this is happening.
        
        [TWIST] - (Strictly 300-350 words). The part most people don't know. The angle that
        makes your video worth watching even if they've heard about this topic before. Elaborate on the implications.
        
        [RESOLUTION] - (Strictly 200-250 words). What does this mean going forward? What should
        the viewer think or feel differently about now? Provide a comprehensive conclusion.
        
        [CTA] - (Strictly 50-75 words). Tell them to watch the next video: "If you want to
        understand [related topic], I've already covered that — link is right there."
        
        Total target: 1,400–1,800 words minimum. Do NOT output a short summary. Write full, lengthy paragraphs.
        
        After the script, on a new line, output a JSON block in this exact format:
        {{"title_options": ["...", "...", "..."], "thumbnail_keywords": ["...", "...", "..."],
         "search_keywords": ["...", "...", "..."], "estimated_duration_minutes": 0}}
        
        The three title_options must use different hooks: one curiosity gap, one number,
        one "nobody is talking about this" framing.
        """
        
        response_text = self._call_llm(system_prompt, user_prompt)
        
        return self._parse_script_response(response_text, topic)

    def _parse_script_response(self, text: str, topic: str) -> dict:
        # Check for missing sections
        missing_sections = [sec for sec in REQUIRED_SECTIONS if sec not in text]
        if missing_sections:
            raise ValueError(f"Missing required sections in LLM response: {', '.join(missing_sections)}")

        # Extract JSON
        json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if not json_match:
            # Fallback to finding anything that looks like JSON
            json_match = re.search(r'(\{[\s\S]*"title_options"[\s\S]*\})', text, re.DOTALL)
            
        if not json_match:
            raise ValueError("Could not find the JSON metadata block in the response.")
            
        json_str = json_match.group(1)
        try:
            metadata = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON metadata block: {e}")

        # Parse sections
        sections = {}
        full_script_parts = []
        
        # We split by section markers
        pattern = r'(\[(?:HOOK|CONTEXT|CONFLICT|EVIDENCE|TWIST|RESOLUTION|CTA)\])'
        parts = re.split(pattern, text)
        
        current_section = None
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if part in REQUIRED_SECTIONS:
                current_section = part[1:-1].lower() # e.g. "hook"
            elif current_section:
                # Remove json block if it was included in the CTA or last section
                clean_part = re.sub(r'```json.*?```', '', part, flags=re.DOTALL)
                clean_part = re.sub(r'\{.*"title_options".*\}', '', clean_part, flags=re.DOTALL)
                clean_part = clean_part.strip()
                if clean_part:
                    sections[current_section] = clean_part
                    full_script_parts.append(clean_part)
                current_section = None
                
        full_script = " ".join(full_script_parts)
        
        result = {
            "topic": topic,
            "sections": sections,
            "metadata": metadata,
            "full_script": full_script
        }
        
        # Save output
        self._save_output(topic, result)
        return result
        
    def _save_output(self, topic: str, data: dict):
        slug = re.sub(r'[^a-z0-9]+', '_', topic.lower()).strip('_')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        out_dir = "output/scripts"
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"{slug}_{timestamp}.json")
        
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
    @llm_retry_decorator()
    def select_best_title(self, title_options: list) -> str:
        if not title_options:
            return "Default Title"
            
        system_prompt = """
        You are a YouTube thumbnail and title analyst.
        Evaluate the title options and choose the highest-CTR title.

        BANNED PHRASES (auto-disqualify any title containing these):
        "Shocking Truth", "You Won't Believe", "This Will Shock You", "Mind Blowing",
        "Incredible", "Amazing", "Jaw Dropping", "Game Changer", "Everything You Know Is Wrong"

        PREFERRED PATTERNS (reward titles that use these):
        - Specific numbers: "3 Reasons Oil Prices Won't Stop Climbing"
        - Named actors + conflict: "Why OPEC's Gamble Is Backfiring on Everyone"  
        - Counterintuitive framing: "Oil Is Getting Cheaper to Produce — So Why Are Prices Rising?"
        - Consequence framing: "The Oil Price Spike That Could Tip the Next Recession"

        Score each option against these rules internally before picking the winner.
        Reply with the EXACT text of the winning title, nothing else.
        """
        user_prompt = f"Choose the best title from these options:\n" + "\n".join([f"- {t}" for t in title_options])
        
        response_text = self._call_llm(system_prompt, user_prompt)
        if not response_text:
            raise ValueError("Empty response for title selection")
            
        best_title = response_text.strip().strip('"').strip("'")
        for t in title_options:
            if best_title.lower() in t.lower() or t.lower() in best_title.lower():
                return t
        return best_title

    @llm_retry_decorator()
    def generate_hook_for_shorts(self, context_text: str) -> str:
        """
        Generates a punchy, 3-second hook text (max 10-15 words) for a Short
        based on the first two sentences of the longform context.
        """
        system_prompt = """
        You are an expert YouTube Shorts scriptwriter. 
        Your goal is to extract a highly engaging, extremely brief hook (under 15 words) 
        from the provided text. It must be punchy, curiosity-inducing, and spoken in 
        under 3 seconds. Do not use quotation marks. Do not use hashtags.
        """
        sentences = re.split(r'(?<=[.!?])\s+', context_text.strip())
        first_two = " ".join(sentences[:2]).strip()
        user_prompt = f"Extract a short hook from this text: {first_two}"
        
        response_text = self._call_llm(system_prompt, user_prompt)
        if not response_text:
            raise ValueError("Empty response for hook generation")
            
        return response_text.strip().strip('"').strip("'")
