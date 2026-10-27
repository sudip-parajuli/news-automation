# Trending Today — Nepali News Automation

RSS collection, Nepali caption preparation and scheduled social publishing for
[Trending Today on Facebook](https://www.facebook.com/ontrending24) and
[Instagram](https://www.instagram.com/ontrendingtoday/).

The current implementation prepares branded image cards and a grouped daily
digest. Older video-generation code is no longer part of this repository's
current application.

## How the current pipeline works

| Phase | Responsibility |
| --- | --- |
| `prepare` | Fetch feeds, skip recorded items, prioritize stories, generate captions/digest lines and queue selected image cards |
| `publish` | Publish queued cards through configured Meta accounts and update recorded publication state |
| `digest` | Group the day's prepared items into a Facebook text digest |

Daily/per-run caps and card retention are configured in `newsbot/config.py`.
Source references are retained alongside prepared content. Hash-based history
reduces repeat processing; it is not a guarantee that paraphrases or concurrent
runs can never create duplicate coverage.

## Local preparation

Use Python 3 and a virtual environment. Install `requirements.txt`, copy
`.env.example` to `.env`, and supply development provider configuration.

```sh
python -m pip install -r requirements.txt
python -m newsbot.main --phase prepare
```

Preparation can call an LLM and write generated files, but it does not itself
request social publication. `publish` and `digest` are external publishing
actions. Images must be reachable at the configured public URL before Meta can
fetch them; the GitHub workflows handle their commit/push stage.

## Source map and operating limits

- `newsbot/rss_sources.py`, `fetch_news.py` — source collection.
- `newsbot/dedupe.py` — history and duplicate tracking.
- `newsbot/caption.py`, `card_image.py` — captions and branded cards.
- `newsbot/main.py` — phase orchestration.
- `.github/workflows/` — scheduled preparation, publication and digest jobs.

Generated summaries require factual and editorial review. Source attribution,
publication rights, model errors, provider quotas and partial platform failures
remain operational responsibilities. No comprehensive automated regression suite
is included; successful workflow runs alone do not verify news accuracy.

## Integration configuration

The retained setup below describes the existing provider and Meta configuration.
Credentials stay in environment variables/GitHub secrets; keep generated content
and history under review when enabling a scheduled run.


## Required GitHub secrets

| Secret | Purpose |
| --- | --- |
| `GEMINI_API_KEY` (+ `GEMINI_API_KEY2`–`5`, optional) | Primary LLM for writing Nepali captions. Extra keys are tried in order if one fails/rate-limits. |
| `GROQ_API_KEY` (+ `GROQ_API_KEY2`–`4`, optional) | Fallback LLM if every Gemini key fails. Extra keys are tried in order too. |
| `META_ACCESS_TOKEN` | Long-lived **Page** access token (see below) |
| `FB_PAGE_ID` | Facebook Page ID for Trending Today |
| `IG_ACCOUNT_ID` | Instagram Business Account ID linked to that Page |

Configure the model provider keys for caption generation. The numbered extras
(`2`, `3`, ...) are optional fallbacks. Social publication additionally requires
the Meta access token and the relevant account IDs listed above.

### Getting `META_ACCESS_TOKEN`, `FB_PAGE_ID`, `IG_ACCOUNT_ID`

1. In [Graph API Explorer](https://developers.facebook.com/tools/explorer/), select your
   app, and request a User access token with: `pages_show_list`, `pages_read_engagement`,
   `pages_manage_posts`, `instagram_basic`, `instagram_content_publish`.
2. Call `GET /me/accounts` to find the Trending Today Page and its **Page access token**
   and `id` (this `id` is `FB_PAGE_ID`).
3. Call `GET /{FB_PAGE_ID}?fields=instagram_business_account` to get `IG_ACCOUNT_ID`.
4. Follow Meta's current [access-token documentation](https://developers.facebook.com/docs/facebook-login/guides/access-tokens/)
   for the appropriate token type, permissions, validity and renewal. Store the
   selected Page token as `META_ACCESS_TOKEN`; do not assume any token is permanent.

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
