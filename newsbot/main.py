"""Orchestrator for the Nepali text+image news poster.

Runs in three phases (see .github/workflows/news_social.yml and
.github/workflows/daily_digest.yml):

  --phase prepare  fetch RSS -> dedupe -> ask the model to write a Nepali
                    caption AND judge significance for each new story ->
                    always log a 1-sentence digest_line_ne into
                    newsbot/data/digest_today.json -> only for stories marked
                    significant (capped at MAX_CARD_POSTS_PER_DAY per rolling
                    24h) render a card image and queue it in
                    newsbot/data/pending.json
                    (workflow then commits+pushes the card images so they are
                    reachable at a public raw.githubusercontent.com URL)

  --phase publish   read pending.json -> post each queued card image + caption
                    to Facebook and Instagram (using the now-live raw URL) ->
                    update newsbot/data/posted_history.json
                    (workflow then commits+pushes the history file)

  --phase digest    once a day: read newsbot/data/digest_today.json -> post ONE
                    grouped Facebook text status covering every story from the
                    day in a sentence or two each -> reset the digest file
                    (workflow then commits+pushes the reset digest file)
"""

import argparse
import glob
import json
import os
import sys
import time
import traceback
from collections import defaultdict

from . import config
from .card_image import generate_card
from .dedupe import already_posted, item_hash, load_history, save_history
from .fetch_news import fetch_all
from .caption import write_caption
from .poster_facebook import post_image as post_facebook_image
from .poster_facebook import post_text as post_facebook_text
from .poster_instagram import post_image as post_instagram_image

REGION_PRIORITY = {"nepal": 0, "nepal_sports": 0, "tech": 1, "intl": 1, "intl_sports": 1}
CATEGORY_PRIORITY = {"tech": 0, "viral": 0, "fake_news": 0, "politics": 0, "sports": 0, "general": 1}

DIGEST_CATEGORY_LABELS = {
    "politics": "राजनीति",
    "tech": "प्रविधि",
    "sports": "खेलकुद",
    "viral": "भाइरल",
    "fake_news": "भ्रामक/फेक न्युज",
    "general": "अन्य समाचार",
}
DIGEST_CATEGORY_ORDER = ["politics", "tech", "sports", "viral", "fake_news", "general"]


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


def build_digest_message(items):
    grouped = defaultdict(list)
    for it in items:
        grouped[it.get("category") or "general"].append(it)

    lines = [f"🗞️ आजका प्रमुख समाचारहरू ({len(items)} समाचार)", ""]

    seen_categories = set()
    for cat in DIGEST_CATEGORY_ORDER:
        cat_items = grouped.get(cat)
        if not cat_items:
            continue
        seen_categories.add(cat)
        lines.append(f"【{DIGEST_CATEGORY_LABELS.get(cat, cat)}】")
        for it in cat_items:
            lines.append(f"• {it['digest_line_ne']}")
        lines.append("")

    for cat, cat_items in grouped.items():
        if cat in seen_categories:
            continue
        lines.append(f"【{DIGEST_CATEGORY_LABELS.get(cat, cat)}】")
        for it in cat_items:
            lines.append(f"• {it['digest_line_ne']}")
        lines.append("")

    lines.append("थप जानकारीको लागि हाम्रो पेज फलो गर्नुहोस्। #TrendingToday")
    return "\n".join(lines).strip()


def _prune_old_cards(keep=None):
    keep = keep or config.MAX_CARD_FILES
    files = sorted(glob.glob(f"{config.CARDS_DIR}/*.jpg"), key=os.path.getmtime)
    for f in files[:-keep] if len(files) > keep else []:
        try:
            os.remove(f)
        except OSError:
            pass


def _load_digest_items():
    if not os.path.exists(config.DIGEST_FILE):
        return []
    try:
        with open(config.DIGEST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def prepare():
    history = load_history()
    items = fetch_all()
    print(f"[prepare] Fetched {len(items)} raw items")

    unseen = [it for it in items if not already_posted(it, history)]
    unseen.sort(key=rank_key)
    print(f"[prepare] {len(unseen)} unseen items after dedupe")

    # How many card posts already went out in the last 24 hours -- this is
    # the daily cap that keeps the page from over-posting.
    cutoff = time.time() - 24 * 3600
    cards_today = sum(
        1 for p in history.get("posted", [])
        if p.get("card_posted") and p.get("posted_at", 0) >= cutoff
    )

    digest_items = _load_digest_items()

    pending = []
    processed = 0
    for item in unseen:
        if processed >= config.MAX_ITEMS_PER_RUN:
            break
        try:
            written = write_caption(item)
            headline = written["headline_ne"]
            caption_text = written["caption_ne"]
            digest_line = written.get("digest_line_ne") or caption_text
            significant = bool(written.get("significant"))
            hashtags = written.get("hashtags", [])
            processed += 1

            item_h = item_hash(item)

            # Every processed story -- significant or not -- gets a one-line
            # entry in the running end-of-day digest.
            digest_items.append({
                "hash": item_h,
                "digest_line_ne": digest_line,
                "source": item["source"],
                "category": item["category"],
                "link": item["link"],
            })

            card_posted = False
            if (
                significant
                and cards_today < config.MAX_CARD_POSTS_PER_DAY
                and len(pending) < config.MAX_POSTS_PER_RUN
            ):
                slug = item_h[:16]
                card_path = f"{config.CARDS_DIR}/{slug}.jpg"
                generate_card(headline, caption_text, card_path)
                message = build_message(headline, caption_text, hashtags, item["link"])
                pending.append({
                    "hash": item_h,
                    "title": item["title"],
                    "link": item["link"],
                    "source": item["source"],
                    "category": item["category"],
                    "card_path": card_path,
                    "message": message,
                })
                cards_today += 1
                card_posted = True

            # Mark as processed immediately so it's never re-picked-up or
            # re-added to the digest, whether or not it got a card post.
            history.setdefault("posted", []).append({
                "hash": item_h,
                "title": item["title"],
                "link": item["link"],
                "source": item["source"],
                "category": item["category"],
                "posted_at": time.time(),
                "card_posted": card_posted,
                "fb_post_id": None,
                "ig_post_id": None,
            })

            label = "CARD" if card_posted else "digest-only"
            print(f"[prepare] {label}: {item['source']} | {item['title'][:80]}")
        except Exception:
            print(f"[prepare] Failed to process item: {item.get('title')}")
            traceback.print_exc()
            continue

    _prune_old_cards()
    save_history(history)

    os.makedirs(os.path.dirname(config.DIGEST_FILE), exist_ok=True)
    with open(config.DIGEST_FILE, "w", encoding="utf-8") as f:
        json.dump(digest_items, f, ensure_ascii=False, indent=2)

    os.makedirs(os.path.dirname(config.PENDING_FILE), exist_ok=True)
    with open(config.PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(pending, f, ensure_ascii=False, indent=2)

    print(
        f"[prepare] Processed {processed} item(s): {len(pending)} card post(s) queued, "
        f"{len(digest_items)} item(s) waiting in today's digest"
    )


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
    by_hash = {p["hash"]: p for p in history.get("posted", [])}
    posted = 0

    for entry in pending:
        image_url = build_raw_url(entry["card_path"])

        fb_id = None
        try:
            fb_id = post_facebook_image(image_url, entry["message"])
            print(f"[publish] Posted to Facebook: {fb_id}")
        except Exception:
            print(f"[publish] Facebook post failed for: {entry['title']}")
            traceback.print_exc()

        ig_id = None
        try:
            ig_id = post_instagram_image(image_url, entry["message"])
            print(f"[publish] Posted to Instagram: {ig_id}")
        except Exception:
            print(f"[publish] Instagram post failed for: {entry['title']}")
            traceback.print_exc()

        record = by_hash.get(entry["hash"])
        if record is not None:
            record["fb_post_id"] = fb_id
            record["ig_post_id"] = ig_id
        if fb_id or ig_id:
            posted += 1

    save_history(history)
    try:
        os.remove(config.PENDING_FILE)
    except OSError:
        pass
    print(f"[publish] Done. Posted {posted}/{len(pending)} card item(s).")


def digest():
    items = _load_digest_items()
    if not items:
        print("[digest] Digest is empty, nothing to post")
        return

    if not config.META_ACCESS_TOKEN or not config.FB_PAGE_ID:
        print("[digest] Missing META_ACCESS_TOKEN/FB_PAGE_ID, aborting without posting")
        sys.exit(1)

    message = build_digest_message(items)
    try:
        post_id = post_facebook_text(message)
        print(f"[digest] Posted daily digest to Facebook ({len(items)} stories): {post_id}")
    except Exception:
        print("[digest] Failed to post daily digest")
        traceback.print_exc()
        sys.exit(1)

    os.makedirs(os.path.dirname(config.DIGEST_FILE), exist_ok=True)
    with open(config.DIGEST_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["prepare", "publish", "digest"], required=True)
    args = parser.parse_args()
    if args.phase == "prepare":
        prepare()
    elif args.phase == "publish":
        publish()
    else:
        digest()


if __name__ == "__main__":
    main()
