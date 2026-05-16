"""
scripts/shorts_script_enhancer.py
==================================
LLM-powered hook text and loop hook generator for YouTube Shorts.

Usage:
    from scripts.shorts_script_enhancer import enhance_shorts_script

    enhanced = enhance_shorts_script(script_text, headline)
    # {"hook_text": "...", "loop_hook": "...", "headline": headline}
"""

import os
import re
import json
import hashlib
from pathlib import Path
from dotenv import load_dotenv
from scripts.llm_utils import call_gemini

load_dotenv()

BANNED_PHRASES = [
    "shocking truth", "you won't believe", "mind blowing", "mind-blowing",
    "game changer", "game-changer", "this will shock you", "incredible", "amazing"
]

OUTPUT_DIR = Path("output/shorts_enhanced")


def _slug(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:12]


# ─── Hook text ────────────────────────────────────────────────────────────────
def generate_hook_text(summary: str) -> str:
    """
    Generate a ≤8-word hook for a YouTube Short.
    Returns the hook_text string. Falls back to a truncated headline if LLM fails.
    """
    system_prompt = (
        "You are an expert YouTube Shorts hook writer. "
        "You only output valid JSON with a single key 'hook_text'. No markdown, no explanation."
    )
    user_prompt = f"""Given this news summary: {summary}

Write a hook_text for a YouTube Short. Max 8 words. Creates urgent curiosity.
BANNED phrases: 'Shocking Truth', 'You Won't Believe', 'Mind Blowing',
'Game Changer', 'This Will Shock You', 'Incredible', 'Amazing'
Preferred patterns:
- Specific consequence: "This crash just changed airport security forever"
- Named actor + conflict: "OPEC just made a $2 trillion mistake"
- Counterintuitive fact: "The rescue team arrived — and made it worse"
Return JSON only: {{"hook_text": "..."}}"""

    try:
        raw = call_gemini(system_prompt, user_prompt, max_output_tokens=128)
        # Strip markdown fences if present
        raw = re.sub(r"```(?:json)?", "", raw).strip()
        parsed = json.loads(raw)
        hook = parsed.get("hook_text", "").strip()
        if not hook:
            raise ValueError("Empty hook_text from LLM")

        # Banned phrase check
        hook_lower = hook.lower()
        for phrase in BANNED_PHRASES:
            if phrase in hook_lower:
                print(f"[ShortEnhancer] Banned phrase '{phrase}' detected — regenerating")
                raise ValueError(f"Hook contains banned phrase: {phrase}")

        # Word count check
        if len(hook.split()) > 8:
            hook = " ".join(hook.split()[:8])

        return hook

    except Exception as e:
        print(f"[ShortEnhancer] generate_hook_text failed: {e}. Using headline fallback.")
        # Truncate summary to 8 words as fallback
        words = summary.split()
        return " ".join(words[:8]) if len(words) > 8 else summary


# ─── Loop hook ────────────────────────────────────────────────────────────────
def generate_loop_hook(hook_text: str) -> str:
    """
    Generate a ≤6-word loop hook that callbacks to the hook_text.
    Makes the last frame feel like the first to encourage replays.
    """
    system_prompt = (
        "You are an expert YouTube Shorts loop hook writer. "
        "You only output valid JSON with a single key 'loop_hook'. No markdown, no explanation."
    )
    user_prompt = f"""Given hook_text: {hook_text}

Write a loop_hook: max 6 words. Callbacks to the hook. Makes the last frame
feel like the first to encourage replays.
Example: hook="OPEC just made a $2 trillion mistake" → loop="That's the $2 trillion mistake."
Return JSON only: {{"loop_hook": "..."}}"""

    try:
        raw = call_gemini(system_prompt, user_prompt, max_output_tokens=64)
        raw = re.sub(r"```(?:json)?", "", raw).strip()
        parsed = json.loads(raw)
        loop = parsed.get("loop_hook", "").strip()
        if not loop:
            raise ValueError("Empty loop_hook from LLM")

        # Word count check
        if len(loop.split()) > 6:
            loop = " ".join(loop.split()[:6])

        return loop

    except Exception as e:
        print(f"[ShortEnhancer] generate_loop_hook failed: {e}. Using hook fallback.")
        words = hook_text.split()
        return " ".join(words[:6]) if len(words) > 6 else hook_text


# ─── Orchestrator ─────────────────────────────────────────────────────────────
def enhance_shorts_script(script_text: str, headline: str) -> dict:
    """
    Generate hook_text and loop_hook for the given short script.
    Saves result to output/shorts_enhanced/{hash}.json.
    Returns {"hook_text": str, "loop_hook": str, "headline": str}.
    """
    # Use headline as the hook generation seed (more punchy than full script)
    summary = headline if headline else script_text[:300]

    hook_text = generate_hook_text(summary)
    loop_hook = generate_loop_hook(hook_text)

    result = {
        "hook_text": hook_text,
        "loop_hook": loop_hook,
        "headline": headline,
    }

    # Persist for debugging / resume
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{_slug(headline)}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"[ShortEnhancer] hook_text: {hook_text!r}")
    print(f"[ShortEnhancer] loop_hook: {loop_hook!r}")

    return result
