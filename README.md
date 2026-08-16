# Trending Today — Nepali News Social Poster

Automated news poster for the **Trending Today** Facebook and Instagram pages:

- Facebook: https://www.facebook.com/ontrending24
- Instagram: https://www.instagram.com/ontrendingtoday/

This repo used to generate and upload YouTube videos. YouTube banned the channel, so the
video pipeline (Remotion, MoviePy, TTS, YouTube upload, etc.) has been removed. The repo
now does one thing: pull real news from RSS feeds, write an original short **Nepali**
caption for each story, and post it as **text** to Facebook and as a **text card image**
to Instagram (Instagram's API does not support pure text posts). No videos, no audio.

## How it works

A GitHub Actions workflow (`.github/workflows/news_social.yml`) runs every 30 minutes:

1. **Fetch** — pull recent items from Nepali RSS feeds (OnlineKhabar, Setopati, Ratopati,
   Nagarik News, Annapurna Post, The Kathmandu Post) and international feeds (BBC, Al
   Jazeera), see `newsbot/rss_sources.py`.
2. **Dedupe** — skip anything already posted before, tracked by hash in
   `newsbot/data/posted_history.json`. The same story is never posted twice.
3. **Prioritize** — Nepal politics and sports first, then other Nepal news, then
   international news.
4. **Write** — Gemini rewrites each story as an original, factual Nepali caption +
   headline + hashtags (`newsbot/caption.py`). If a Gemini key fails or is rate-limited,
   it automatically tries the next `GEMINI_API_KEY2/3/4/5`, then falls back to
   `GROQ_API_KEY` and its extra keys the same way — one working key is enough to keep
   the run going.
5. **Render** — a branded 1080×1350 text card image is generated for Instagram with
   Pillow (`newsbot/card_image.py`). Facebook gets a plain text post.
6. **Publish** — posts the text to the Facebook Page feed, and the card image + caption
   to Instagram via the Graph API two-step container flow (`newsbot/poster_facebook.py`,
   `newsbot/poster_instagram.py`).

There's no fixed number of posts per day — every run posts whatever unseen stories it
finds, capped at `MAX_POSTS_PER_RUN` (default 6) per run to avoid bursts.

## Required GitHub secrets

| Secret | Purpose |
| --- | --- |
| `GEMINI_API_KEY` (+ `GEMINI_API_KEY2`–`5`, optional) | Primary LLM for writing Nepali captions. Extra keys are tried in order if one fails/rate-limits. |
| `GROQ_API_KEY` (+ `GROQ_API_KEY2`–`4`, optional) | Fallback LLM if every Gemini key fails. Extra keys are tried in order too. |
| `META_ACCESS_TOKEN` | Long-lived **Page** access token (see below) |
| `FB_PAGE_ID` | Facebook Page ID for Trending Today |
| `IG_ACCOUNT_ID` | Instagram Business Account ID linked to that Page |

Only `GEMINI_API_KEY` and `GROQ_API_KEY` are required; the numbered extras (`2`, `3`, ...)
are optional fallbacks — add as many or as few as you have.

### Getting `META_ACCESS_TOKEN`, `FB_PAGE_ID`, `IG_ACCOUNT_ID`

1. In [Graph API Explorer](https://developers.facebook.com/tools/explorer/), select your
   app, and request a User access token with: `pages_show_list`, `pages_read_engagement`,
   `pages_manage_posts`, `instagram_basic`, `instagram_content_publish`.
2. Call `GET /me/accounts` to find the Trending Today Page and its **Page access token**
   and `id` (this `id` is `FB_PAGE_ID`).
3. Call `GET /{FB_PAGE_ID}?fields=instagram_business_account` to get `IG_ACCOUNT_ID`.
4. Exchange the Page access token for a **long-lived** token (Meta's
   [access token guide](https://developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived))
   so it doesn't expire every ~60 days, or generate it from a System User in a Meta
   Business Portfolio for a token that effectively doesn't expire. Use that value as
   `META_ACCESS_TOKEN`.

### Required repo setting

**Settings → Actions → General → Workflow permissions** must be set to
**"Read and write permissions"** — the workflow commits the generated card images and
the updated history file back to the repo, and needs push access to do that.

## Running locally

```
cp .env.example .env   # fill in the values
pip install -r requirements.txt
python -m newsbot.main --phase prepare
python -m newsbot.main --phase publish
```

Note: `--phase publish` posts the Instagram image by URL
(`raw.githubusercontent.com/...`), so locally it only works for images that have
already been committed and pushed to GitHub.
