"""
scripts/llm_utils.py
====================
Shared LLM utility providing GeminiKeyRotator for 4-key round-robin rotation
with per-key cooldowns, and a Groq fallback when all Gemini keys are exhausted.

Usage:
    from scripts.llm_utils import call_gemini

    text = call_gemini(system_prompt, user_prompt)
"""

import os
import time
import groq
from google import genai


class GeminiKeyRotator:
    """
    Round-robin rotator across up to 4 Gemini API keys.

    Cooldown policy:
    - 429 / RESOURCE_EXHAUSTED (transient):  60s cooldown
    - Daily quota exhausted ("GenerateRequestsPerDay" in error): 3600s cooldown
    """

    DAILY_QUOTA_MARKER = "GenerateRequestsPerDay"

    def __init__(self):
        self.keys = []
        for suffix in ["", "2", "3", "4", "5", "6", "7", "8", "9", "10"]:
            key = os.getenv(f"GEMINI_API_KEY{suffix}")
            if key:
                name = f"GEMINI_API_KEY{suffix if suffix else '1'}"
                self.keys.append({
                    "key": key,
                    "name": name,
                    "cooldown_until": 0.0,
                })

        if not self.keys:
            raise ValueError("No GEMINI_API_KEY found in environment")

        self.current_idx = 0
        print(f"[GeminiKeyRotator] Loaded {len(self.keys)} Gemini key(s): "
              f"{[k['name'] for k in self.keys]}")

    # ── Key retrieval ──────────────────────────────────────────────────────────
    def get_client(self):
        """
        Return (genai.Client, key_name) for the next available key.
        Blocks (with a short sleep) only if all keys are in cooldown.
        """
        if not self.keys:
            raise ValueError("No Gemini keys available")

        start_idx = self.current_idx
        while True:
            entry = self.keys[self.current_idx]
            self.current_idx = (self.current_idx + 1) % len(self.keys)

            if time.time() >= entry["cooldown_until"]:
                client = genai.Client(api_key=entry["key"])
                return client, entry["name"]

            # If we've looped through all keys, wait for the earliest to free
            if self.current_idx == start_idx:
                earliest = min(k["cooldown_until"] for k in self.keys)
                wait = earliest - time.time()
                if wait > 0:
                    print(f"[GeminiKeyRotator] All keys rate-limited. "
                          f"Waiting {wait:.1f}s for earliest key to free...")
                    time.sleep(min(wait, 60))  # cap sleep at 60s per iteration

    # ── Cooldown setters ───────────────────────────────────────────────────────
    def mark_rate_limit(self, key_val: str):
        """Mark a key as rate-limited (60s cooldown)."""
        self._set_cooldown(key_val, 60.0)

    def mark_quota_exhausted(self, key_val: str):
        """Mark a key as daily-quota-exhausted (1hr cooldown)."""
        self._set_cooldown(key_val, 3600.0)

    def _set_cooldown(self, key_val: str, seconds: float):
        for entry in self.keys:
            if entry["key"] == key_val:
                entry["cooldown_until"] = time.time() + seconds
                print(f"[GeminiKeyRotator] {entry['name']} cooling down for {seconds:.0f}s")
                break

    def all_exhausted(self) -> bool:
        """True when every key is currently in cooldown."""
        return all(time.time() < k["cooldown_until"] for k in self.keys)


# ── Module-level singleton ─────────────────────────────────────────────────────
_rotator: GeminiKeyRotator | None = None

def _get_rotator() -> GeminiKeyRotator:
    global _rotator
    if _rotator is None:
        _rotator = GeminiKeyRotator()
    return _rotator


# ── Groq Key Rotator ──────────────────────────────────────────────────────────
class GroqKeyRotator:
    def __init__(self):
        self.keys = []
        for suffix in ["", "2", "3", "4", "5", "6", "7", "8", "9", "10"]:
            key = os.getenv(f"GROQ_API_KEY{suffix}")
            if key:
                name = f"GROQ_API_KEY{suffix if suffix else '1'}"
                self.keys.append({
                    "key": key,
                    "name": name,
                    "cooldown_until": 0.0,
                })

        if not self.keys:
            print("[GroqKeyRotator] WARNING: No GROQ_API_KEY found in environment")
        else:
            print(f"[GroqKeyRotator] Loaded {len(self.keys)} Groq key(s): "
                  f"{[k['name'] for k in self.keys]}")

        self.current_idx = 0

    def get_client(self):
        if not self.keys:
            raise ValueError("No Groq keys available")

        start_idx = self.current_idx
        while True:
            entry = self.keys[self.current_idx]
            self.current_idx = (self.current_idx + 1) % len(self.keys)

            if time.time() >= entry["cooldown_until"]:
                client = groq.Groq(api_key=entry["key"])
                return client, entry["name"]

            if self.current_idx == start_idx:
                earliest = min(k["cooldown_until"] for k in self.keys)
                wait = earliest - time.time()
                if wait > 0:
                    print(f"[GroqKeyRotator] All keys rate-limited. "
                          f"Waiting {wait:.1f}s for earliest key to free...")
                    time.sleep(min(wait, 60))

    def mark_rate_limit(self, key_val: str, seconds: float = 60.0):
        for entry in self.keys:
            if entry["key"] == key_val:
                entry["cooldown_until"] = time.time() + seconds
                print(f"[GroqKeyRotator] {entry['name']} cooling down for {seconds:.0f}s")
                break

    def all_exhausted(self) -> bool:
        if not self.keys:
            return True
        return all(time.time() < k["cooldown_until"] for k in self.keys)

_groq_rotator: GroqKeyRotator | None = None

def _get_groq_rotator() -> GroqKeyRotator:
    global _groq_rotator
    if _groq_rotator is None:
        _groq_rotator = GroqKeyRotator()
    return _groq_rotator


# ── Groq fallback ─────────────────────────────────────────────────────────────
def _call_groq(system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
    rotator = _get_groq_rotator()
    if not rotator.keys:
        raise ValueError("GROQ_API_KEY not set — cannot fall back to Groq")
        
    max_attempts = len(rotator.keys) * 2 + 1
    last_error = None
    current_key_val = None

    for attempt in range(max_attempts):
        if rotator.all_exhausted():
            raise RuntimeError("All Groq keys exhausted.")
            
        try:
            client, key_name = rotator.get_client()
            current_key_val = next(
                (k["key"] for k in rotator.keys if k["name"] == key_name), None
            )
            print(f"[GroqKeyRotator] Attempt {attempt + 1} via {key_name}")

            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
            )
            if not completion or not completion.choices:
                raise ValueError("Empty response from Groq")
            return completion.choices[0].message.content
            
        except Exception as e:
            err = str(e)
            last_error = e
            print(f"[GroqKeyRotator] {key_name} failed: {err[:120]}")
            
            if current_key_val:
                if "429" in err or "rate_limit" in err.lower():
                    rotator.mark_rate_limit(current_key_val, 60.0)
                elif "tokens per day" in err.lower():
                    rotator.mark_rate_limit(current_key_val, 3600.0)

    raise RuntimeError(f"All {max_attempts} Groq attempts failed. Last error: {last_error}") from last_error


# ── Public helper ─────────────────────────────────────────────────────────────
def call_gemini(
    system_prompt: str,
    user_prompt: str,
    model: str = "gemini-2.0-flash",
    max_output_tokens: int = 4096,
    max_attempts: int = None,
) -> str:
    """
    Call Gemini with automatic key rotation.

    - Tries all available Gemini keys in round-robin order.
    - On 429 or RESOURCE_EXHAUSTED: marks key with 60s cooldown, tries next.
    - On daily quota error: marks key with 3600s cooldown, tries next.
    - Falls back to Groq only when ALL Gemini keys are exhausted simultaneously.
    - Raises if both Gemini and Groq fail.
    """
    rotator = _get_rotator()
    max_attempts = max_attempts or (len(rotator.keys) * 2 + 1)
    last_error = None
    current_key_val = None

    for attempt in range(max_attempts):
        if rotator.all_exhausted():
            print("[GeminiKeyRotator] All Gemini keys exhausted — falling back to Groq")
            return _call_groq(system_prompt, user_prompt, max_output_tokens)

        try:
            client, key_name = rotator.get_client()
            # Store the current key value for cooldown marking on error
            current_key_val = next(
                (k["key"] for k in rotator.keys if k["name"] == key_name), None
            )
            print(f"[GeminiKeyRotator] Attempt {attempt + 1} via {key_name}")

            response = client.models.generate_content(
                model=model,
                contents=[system_prompt, user_prompt],
                config=genai.types.GenerateContentConfig(
                    max_output_tokens=max_output_tokens
                ),
            )
            if not response or not response.text:
                raise ValueError("Empty response from Gemini")
            return response.text

        except Exception as e:
            err = str(e)
            last_error = e
            print(f"[GeminiKeyRotator] {key_name} failed: {err[:120]}")

            if current_key_val:
                if GeminiKeyRotator.DAILY_QUOTA_MARKER in err:
                    rotator.mark_quota_exhausted(current_key_val)
                elif "429" in err or "ResourceExhausted" in err or "RESOURCE_EXHAUSTED" in err:
                    rotator.mark_rate_limit(current_key_val)
                # Other errors (network, etc.) don't trigger cooldown

    # All Gemini attempts failed — try Groq as last resort
    print(f"[GeminiKeyRotator] All {max_attempts} Gemini attempts failed. Trying Groq...")
    try:
        return _call_groq(system_prompt, user_prompt, max_output_tokens)
    except Exception as groq_err:
        raise RuntimeError(
            f"Both Gemini and Groq failed. Last Gemini error: {last_error}. "
            f"Groq error: {groq_err}"
        ) from last_error
