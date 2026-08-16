import requests

from . import config


def post_text(message):
    """Publish a plain text post to the Facebook Page feed."""
    url = f"https://graph.facebook.com/{config.GRAPH_API_VERSION}/{config.FB_PAGE_ID}/feed"
    resp = requests.post(
        url,
        data={"message": message, "access_token": config.META_ACCESS_TOKEN},
        timeout=30,
    )
    data = resp.json()
    if resp.status_code >= 400 or "error" in data:
        raise RuntimeError(f"Facebook post failed: {data}")
    return data.get("id")
