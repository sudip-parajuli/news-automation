import os

# Meta Graph API version. Bump this every ~1-2 years; Meta keeps old
# versions alive for about 2 years after release.
GRAPH_API_VERSION = "v23.0"

def _collect_keys(prefix, max_n=10):
    """Collect PREFIX, PREFIX2, PREFIX3, ... env vars into an ordered list
    (skipping any that aren't set), so we can round-robin/fall back across
    multiple API keys for the same provider."""
    keys = []
    first = os.environ.get(prefix, "")
    if first:
        keys.append(first)
    for i in range(2, max_n + 1):
        val = os.environ.get(f"{prefix}{i}", "")
        if val:
            keys.append(val)
    return keys


# Multiple keys per provider are supported (GEMINI_API_KEY, GEMINI_API_KEY2, ...
# and GROQ_API_KEY, GROQ_API_KEY2, ...) so that if one key hits a rate limit or
# quota error, caption.py can fall back to the next one automatically.
GEMINI_API_KEYS = _collect_keys("GEMINI_API_KEY")
GROQ_API_KEYS = _collect_keys("GROQ_API_KEY")

# Back-compat single-key aliases (first key in each list, if any).
GEMINI_API_KEY = GEMINI_API_KEYS[0] if GEMINI_API_KEYS else ""
GROQ_API_KEY = GROQ_API_KEYS[0] if GROQ_API_KEYS else ""

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "")
IG_ACCOUNT_ID = os.environ.get("IG_ACCOUNT_ID", "")

# Used to build a public raw.githubusercontent.com URL for the generated
# Instagram card image (Instagram's API requires a publicly reachable URL).
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "sudip-parajuli/news-automation")
GITHUB_REF_NAME = os.environ.get("GITHUB_REF_NAME", "main")

# How many new stories to post in a single workflow run. The workflow runs
# every 30 minutes, so this caps the max posting rate without hard-limiting
# daily volume.
MAX_POSTS_PER_RUN = int(os.environ.get("MAX_POSTS_PER_RUN", "6"))

# Only consider RSS items published within this many hours.
MAX_ITEM_AGE_HOURS = int(os.environ.get("MAX_ITEM_AGE_HOURS", "36"))

HISTORY_FILE = "newsbot/data/posted_history.json"
CARDS_DIR = "newsbot/data/cards"
PENDING_FILE = "newsbot/data/pending.json"
MAX_HISTORY_ENTRIES = 4000
MAX_CARD_FILES = 500
