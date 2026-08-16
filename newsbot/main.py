"""Orchestrator for the Nepali text+image news poster.

Runs in two phases (see .github/workflows/news_social.yml):

  --phase prepare  fetch RSS -> dedupe -> write Nepali captions -> render card
                    images -> save newsbot/data/pending.json
                    (workflow then commits+pushes the card images so they are
                    reachable at a public raw.githubusercontent.com URL)

  --phase publish   read pending.json -> post text to Facebook -> post image
                    to Instagram (using the now-live raw URL) -> update
                    newsbot/data/posted_history.json
                    (workflow then commits+pushes the history file)
"""

import argparse
import glob
import json
import os
import sys
import time
import traceback

from . import config
from .card_image import generate_card
from .dedupe import already_posted, item_hash, load_history, save_history
from .fetch_news import fetch_all
from .caption import write_caption
from .poster_facebook import post_text
from .poster_instagram import post_image

CATEGORY_LABELS = {"politics": "राजनीति", "sports": "खेलकुद", "general": "समाचार"}
REGION_PRIORITY = {"nepal": 0, "nepal_sports": 0, "intl": 1, "intl_sports": 1}
CATEGORY_PRIORITY = {"politics": 0, "sports": 0, "general": 1}


def rank_key(item):
    return (
        REGION_PRIORITY.get(item["region"], 2),
        CATEGORY_PRIORITY.get(item["category"], 2),
        -item["published_ts"],
    )


def build_raw_url(path):
    return f"https://raw.githubusercontent.com/{config.GITHUB_REPOSITORY}/{config.GITHUB_REF_NAME}/{path}"


def build_message(headline, caption, hashtags, link):
    tag_line = " ".join(f"#{t.strip().replace(' ', '')}" for t in hashtags if t and t.strip())
    parts = [headline, "", caption, "", f"पूरा समाचार / Full story: {link}"]
    if tag_line:
        parts += ["", tag_line]
    return "\n".join(parts)


def _prune_old_cards(keep=None):
    keep = keep or config.MAX_CARD_FILES
    files = sorted(glob.glob(f"{config.CARDS_DIR}/*.jpg"), key=os.path.getmtime)
    for f in files[:-keep] if len(files) > keep else []:
        try:
            os.remove(f)
        except OSError:
            pass


def prepare():
    history = load_history()
    items = fetch_all()
    print(f"[prepare] Fetched {len(items)} raw items")

    unseen = [it for it in items if not already_posted(it, history)]
    unseen.sort(key=rank_key)
    print(f"[prepare] {len(unseen)} unseen items after dedupe")

    pending = []
    for item in unseen:
        if len(pending) >= config.MAX_POSTS_PER_RUN:
            break
        try:
            written = write_caption(item)
            headline = written["headline_ne"]
            caption_text = written["caption_ne"]
            hashtags = written.get("hashtags", [])
            category_label = CATEGORY_LABELS.get(item["category"], "समाचार")

            slug = item_hash(item)[:16]
            card_path = f"{config.CARDS_DIR}/{slug}.jpg"
            generate_card(headline, item["source"], category_label, card_path)

            message = build_message(headline, caption_text, hashtags, item["link"])
            pending.append({
                "hash": item_hash(item),
                "title": item["title"],
                "link": item["link"],
                "source": item["source"],
                "category": item["category"],
                "card_path": card_path,
                "message": message,
            })
            print(f"[prepare] Ready: {item['source']} | {item['title'][:80]}")
        except Exception:
            print(f"[prepare] Failed to process item: {item.get('title')}")
            traceback.print_exc()
            continue

    _prune_old_cards()
    os.makedirs(os.path.dirname(config.PENDING_FILE), exist_ok=True)
    with open(config.PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(pending, f, ensure_ascii=False, indent=2)
    print(f"[prepare] Prepared {len(pending)} item(s) for publishing")


def publish():
    if not os.path.exists(config.PENDING_FILE):
        print("[publish] No pending file found, nothing to publish")
        return

    with open(config.PENDING_FILE, "r", encoding="utf-8") as f:
        pending = json.load(f)

    if not pending:
        print("[publish] Pending list is empty, nothing to publish")
        os.remove(config.PENDING_FILE)
        return

    missing = [k for k in ["META_ACCESS_TOKEN", "FB_PAGE_ID", "IG_ACCOUNT_ID"] if not getattr(config, k)]
    if missing:
        print(f"[publish] Missing required secrets: {missing}. Aborting without posting.")
        sys.exit(1)

    history = load_history()
    posted = 0

    for entry in pending:
        fb_id = None
        try:
            fb_id = post_text(entry["message"])
            print(f"[publish] Posted to Facebook: {fb_id}")
        except Exception:
            print(f"[publish] Facebook post failed for: {entry['title']}")
            traceback.print_exc()

        ig_id = None
        try:
            image_url = build_raw_url(entry["card_path"])
            ig_id = post_image(image_url, entry["message"])
            print(f"[publish] Posted to Instagram: {ig_id}")
        except Exception:
            print(f"[publish] Instagram post failed for: {entry['title']}")
            traceback.print_exc()

        history.setdefault("posted", []).append({
            "hash": entry["hash"],
            "title": entry["title"],
            "link": entry["link"],
            "source": entry["source"],
            "category": entry["category"],
            "posted_at": time.time(),
            "fb_post_id": fb_id,
            "ig_post_id": ig_id,
        })
        if fb_id or ig_id:
            posted += 1

    save_history(history)
    try:
        os.remove(config.PENDING_FILE)
    except OSError:
        pass
    print(f"[publish] Done. Posted {posted}/{len(pending)} item(s).")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["prepare", "publish"], required=True)
    args = parser.parse_args()
    if args.phase == "prepare":
        prepare()
    else:
        publish()


if __name__ == "__main__":
    main()
