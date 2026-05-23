import os
import json
import re
from datetime import datetime
from scripts.llm_utils import call_gemini
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
        # api_key kept for backwards-compat but ignored — GeminiKeyRotator handles rotation
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.groq_client = None
        if self.groq_api_key:
            self.groq_client = groq.Groq(api_key=self.groq_api_key)
        self.groq_model_name = 'llama-3.3-70b-versatile'

    @llm_retry_decorator()
    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        return call_gemini(system_prompt, user_prompt)

    @llm_retry_decorator()
    def _classify_topic(self, topic: str) -> str:
        system_prompt = """
        Classify this YouTube video topic into one of two types:
        - "narrative": suits a documentary/explainer format with conflict and twist
          (examples: "Why oil prices are rising", "How AI is changing jobs")
        - "listicle": suits a ranked list or comparison format
          (examples: "Top 10 airlines", "Best countries for retirement", "Richest people")
        Reply with only one word: narrative or listicle
        """
        user_prompt = f"Topic: {topic}"
        response = self._call_llm(system_prompt, user_prompt).strip().lower()
        if "listicle" in response:
            return "listicle"
        return "narrative"

    def generate_script(self, topic: str) -> dict:
        topic_type = self._classify_topic(topic)
        print(f"Classified topic '{topic}' as: {topic_type}")
        
        if topic_type == "listicle":
            system_prompt = """
            You are a YouTube scriptwriter specializing in countdown and ranking videos.
            Your scripts are structured like a Top 10 countdown: you tease the #1 pick
            in the opener, count down from the lowest rank to #1, and reveal the top
            pick last with the most detail. Each entry gets its own mini-story — one
            surprising fact, one specific detail viewers don't know, and why it matters.
            Tone: authoritative, enthusiastic, like a knowledgeable friend revealing
            insider knowledge. Never read like a Wikipedia article.
            Every section MUST meet its minimum word count. Write in full sentences.
            """
            user_prompt = f"""IMPORTANT: You MUST use the exact section headers shown below (e.g. [HOOK], [ENTRY_10], [ENTRY_9], ... [ENTRY_1], [CTA]). Do NOT use any other headers.

Write a YouTube countdown script for: {topic}

[HOOK]
30 seconds. Tease the #1 pick without naming it. End with: "Let's count down."

[ENTRY_10]
Name and rank clearly stated. One surprising fact. One specific statistic with a number. Why it matters. (150-200 words)

[ENTRY_9]
(same structure as ENTRY_10)

[ENTRY_8]
(same structure)

[ENTRY_7]
(same structure)

[ENTRY_6]
(same structure)

[ENTRY_5]
(same structure)

[ENTRY_4]
(same structure)

[ENTRY_3]
(same structure)

[ENTRY_2]
(same structure)

[ENTRY_1]
This is the #1 pick — give it the most detail. (200-250 words)

[CTA]
15 seconds. Tell viewers to watch the next video.

Total target: 1,400–2,000 words. Write full paragraphs, NOT bullet points.

After the script, output a JSON block:
```json
{{"title_options": ["...", "...", "..."], "thumbnail_keywords": ["...", "...", "..."],
 "search_keywords": ["...", "...", "..."], "estimated_duration_minutes": 0,
 "best_title_index": 0, "best_title_reasoning": "...", "entries": ["Entry name 10", "Entry name 9", "Entry name 8", "Entry name 7", "Entry name 6", "Entry name 5", "Entry name 4", "Entry name 3", "Entry name 2", "Entry name 1"]}}
```
The entries array must list the ranked items in countdown order (ENTRY_10 item first, ENTRY_1 item last).
"""
        else:
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
             "search_keywords": ["...", "...", "..."], "estimated_duration_minutes": 0,
             "best_title_index": 0, "best_title_reasoning": "one sentence explaining why"}}
            
            The three title_options must use different hooks: one curiosity gap, one number,
            one "nobody is talking about this" framing. Also rank the 3 title options you generate and mark the best one using best_title_index (0, 1, or 2).
            """
        
        response_text = self._call_llm(system_prompt, user_prompt)

        try:
            result = self._parse_script_response(response_text, topic)
        except ValueError as parse_err:
            # Print first 2000 chars of the response to help diagnose format issues
            print(f"[Script Parser] Parse failed: {parse_err}")
            print(f"[Script Parser] Raw response (first 2000 chars):\n{response_text[:2000]}")
            raise
        result["topic_type"] = topic_type
        return result


    def _parse_script_response(self, text: str, topic: str) -> dict:
        # Extract JSON metadata block before parsing sections
        json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if not json_match:
            # Fallback: bare JSON object containing title_options
            json_match = re.search(r'(\{[\s\S]*?"title_options"[\s\S]*?\})', text, re.DOTALL)

        if not json_match:
            raise ValueError("Could not find the JSON metadata block in the response.")

        json_str = json_match.group(1)
        try:
            metadata = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON metadata block: {e}")

        # Parse sections — split on every header tag, then accumulate ALL text
        # between consecutive headers (not just the first paragraph).
        pattern = r'(\[(?:HOOK|CONTEXT|CONFLICT|EVIDENCE|TWIST|RESOLUTION|CTA|ENTRY_\d+)\])'
        parts = re.split(pattern, text)

        sections = {}
        accumulator = []   # collects text fragments belonging to current_section
        current_section = None

        def _flush(sec_key, fragments):
            """Clean and store accumulated text for a section."""
            combined = " ".join(fragments)
            # Strip out the JSON block if it leaked into the last section
            combined = re.sub(r'```json.*?```', '', combined, flags=re.DOTALL)
            combined = re.sub(r'\{[\s\S]*?"title_options"[\s\S]*?\}', '', combined, flags=re.DOTALL)
            combined = combined.strip()
            if combined:
                sections[sec_key] = combined

        for part in parts:
            stripped = part.strip()
            if not stripped:
                continue
            if re.match(r'^\[(?:HOOK|CONTEXT|CONFLICT|EVIDENCE|TWIST|RESOLUTION|CTA|ENTRY_\d+)\]$', stripped):
                # Save whatever we accumulated for the previous section
                if current_section is not None and accumulator:
                    _flush(current_section, accumulator)
                current_section = stripped[1:-1].lower()  # e.g. "hook", "entry_10"
                accumulator = []
            elif current_section is not None:
                accumulator.append(stripped)

        # Flush the last section
        if current_section is not None and accumulator:
            _flush(current_section, accumulator)

        # Validate required sections
        is_listicle = any(k.startswith("entry_") for k in sections.keys())
        if is_listicle:
            missing = [s for s in ("hook", "cta") if s not in sections]
            if missing:
                raise ValueError(f"Missing required listicle sections: {', '.join(missing)}")
            entry_count = sum(1 for k in sections if k.startswith("entry_"))
            if entry_count == 0:
                raise ValueError("Listicle script has no ENTRY_N sections.")
        else:
            missing_sections = [sec[1:-1].lower() for sec in REQUIRED_SECTIONS if sec[1:-1].lower() not in sections]
            if missing_sections:
                raise ValueError(f"Missing required sections in LLM response: {', '.join(missing_sections)}")

        full_script = " ".join(sections.values())

        result = {
            "topic": topic,
            "sections": sections,
            "metadata": metadata,
            "full_script": full_script
        }

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
        # DEPRECATED: Title selection is now batched in the script generation step
        # via the 'best_title_index' JSON field. This function remains for A/B testing
        # or fallback if needed in the future.
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
