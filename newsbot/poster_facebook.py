import requests

from . import config


def post_image(image_url, caption):
    """Publish a photo (with caption) to the Facebook Page.

    `image_url` must already be publicly reachable (e.g. a raw.githubusercontent.com
    URL for a file that has been committed and pushed) -- Facebook fetches the
    image itself, it does not accept an upload body here.
    """
    url = f"https://graph.facebook.com/{config.GRAPH_API_VERSION}/{config.FB_PAGE_ID}/photos"
    resp = requests.post(
        url,
        data={"url": image_url, "caption": caption, "access_token": config.META_ACCESS_TOKEN},
        timeout=30,
    )
    data = resp.json()
    if resp.status_code >= 400 or "error" in data:
        raise RuntimeError(f"Facebook post failed: {data}")
    return data.get("post_id") or data.get("id")


def post_text(message):
    """Publish a plain text status update to the Facebook Page.

    Used for the once-daily round-up digest post (all of the day's stories in
    short form), separate from the individual card/photo posts.
    """
    url = f"https://graph.facebook.com/{config.GRAPH_API_VERSION}/{config.FB_PAGE_ID}/feed"
    resp = requests.post(
        url,
        data={"message": message, "access_token": config.META_ACCESS_TOKEN},
        timeout=30,
    )
    data = resp.json()
    if resp.status_code >= 400 or "error" in data:
        raise RuntimeError(f"Facebook text post failed: {data}")
    return data.get("id")
