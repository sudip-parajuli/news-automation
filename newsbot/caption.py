import json
import re

from . import config

PROMPT_TEMPLATE = """You are the news editor for a Nepali Facebook/Instagram page called "Trending Today" (covers Nepal politics/sports, general Nepal news, international news, technology, viral/trending stories, and fact-checks that debunk fake news/misinformation).

Rewrite the following news item as an ORIGINAL short news post written in the NEPALI language (Devanagari script). Do not translate word-for-word -- write it naturally, the way a Nepali news page would: factual, neutral, no clickbait, no emoji spam.

The headline must stay faithful to the ORIGINAL TITLE below -- adapt it into natural Nepali, but do not invent a different angle or add facts that aren't in the source.

Category hint from our own classifier: {category}
Source: {source}
Original title: {title}
Original summary: {summary}
Link: {link}

Also judge whether this story is SIGNIFICANT enough to deserve its own big graphic card post (not just a line in the end-of-day round-up). Mark significant=true ONLY if it is major breaking news, an important government/political decision, a major sports result or upset, a notable technology launch or development, a genuinely viral/trending story, or an important fact-check that debunks real misinformation. Mark significant=false for routine, minor, or low-interest news -- most stories should be false; be selective, we only want the best few stories of the day as card posts.

Return ONLY a JSON object with these exact keys, and nothing else:
{{
  "headline_ne": "a short Nepali headline in Devanagari script, faithful to the original title above, max 12 words, no hashtags, no emoji",
  "caption_ne": "a factual Nepali news summary in Devanagari script, 2 to 3 sentences (never more than 3), longer and more detailed than the headline",
  "digest_line_ne": "the same story compressed into just 1 sentence (max 2 short sentences) of Devanagari Nepali, for a bullet point in an end-of-day round-up post",
  "significant": true or false (boolean, see criteria above),
  "hashtags": ["3 to 5 relevant hashtags without the # symbol"]
}}
"""


def _extract_json(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in model output: {text[:200]!r}")
    return json.loads(match.group(0))


def _call_gemini(prompt, api_key, model):
    from google import genai

    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(model=model, contents=prompt)
    return resp.text


def _call_groq(prompt, api_key, model):
    from groq import Groq

    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content


def write_caption(item):
    prompt = PROMPT_TEMPLATE.format(
        category=item.get("category") or "general",
        source=item.get("source"),
        title=item.get("title"),
        summary=item.get("summary") or "(no summary provided)",
        link=item.get("link"),
    )

    last_err = None

    # Try every configured Gemini key against the primary model first, then
    # every key against the fallback model, then do the same for Groq. This
    # way neither a single rate-limited/expired key NOR a single retired
    # model name can stop the whole run.
    for model in config.GEMINI_MODELS:
        for i, key in enumerate(config.GEMINI_API_KEYS, start=1):
            try:
                return _extract_json(_call_gemini(prompt, key, model))
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                print(f"[caption] Gemini {model} key #{i} failed, trying next: {exc}")

    for model in config.GROQ_MODELS:
        for i, key in enumerate(config.GROQ_API_KEYS, start=1):
            try:
                return _extract_json(_call_groq(prompt, key, model))
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                print(f"[caption] Groq {model} key #{i} failed, trying next: {exc}")

    raise RuntimeError(f"All caption providers/keys/models failed: {last_err}")
