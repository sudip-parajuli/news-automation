import json
import re

from . import config

PROMPT_TEMPLATE = """You are the news editor for a Nepali Facebook/Instagram page called "Trending Today".
Rewrite the following news item as an ORIGINAL short news post written in the NEPALI \
language (Devanagari script). Do not translate word-for-word -- write it naturally, the \
way a Nepali news page would: factual, neutral, no clickbait, no emoji spam.

Source: {source}
Original title: {title}
Original summary: {summary}
Link: {link}

Return ONLY a JSON object with these exact keys, and nothing else:
{{
  "headline_ne": "a short punchy Nepali headline, max 12 words, no hashtags, no emoji",
  "caption_ne": "a 2-4 sentence Nepali caption/summary for a social media post",
  "hashtags": ["3 to 5 relevant hashtags without the # symbol"]
}}
"""


def _extract_json(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in model output: {text[:200]!r}")
    return json.loads(match.group(0))


def _call_gemini(prompt, api_key):
    from google import genai

    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(model=config.GEMINI_MODEL, contents=prompt)
    return resp.text


def _call_groq(prompt, api_key):
    from groq import Groq

    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model=config.GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content


def write_caption(item):
    prompt = PROMPT_TEMPLATE.format(
        source=item.get("source"),
        title=item.get("title"),
        summary=item.get("summary") or "(no summary provided)",
        link=item.get("link"),
    )

    last_err = None

    # Try every configured Gemini key first (GEMINI_API_KEY, GEMINI_API_KEY2, ...),
    # then every configured Groq key, before giving up. This way a single
    # rate-limited/expired key doesn't stop the whole run.
    for i, key in enumerate(config.GEMINI_API_KEYS, start=1):
        try:
            return _extract_json(_call_gemini(prompt, key))
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            print(f"[caption] Gemini key #{i} failed, trying next: {exc}")

    for i, key in enumerate(config.GROQ_API_KEYS, start=1):
        try:
            return _extract_json(_call_groq(prompt, key))
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            print(f"[caption] Groq key #{i} failed, trying next: {exc}")

    raise RuntimeError(f"All caption providers/keys failed: {last_err}")
