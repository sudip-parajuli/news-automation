import time

import requests

from . import config


def post_image(image_url, caption):
    """Publish an image + caption to Instagram via the two-step container API.

    `image_url` must already be publicly reachable (e.g. a raw.githubusercontent.com
    URL for a file that has been committed and pushed) -- Instagram's servers fetch
    the image themselves, they do not accept an upload body.
    """
    base = f"https://graph.facebook.com/{config.GRAPH_API_VERSION}/{config.IG_ACCOUNT_ID}"

    create_resp = requests.post(
        f"{base}/media",
        data={"image_url": image_url, "caption": caption, "access_token": config.META_ACCESS_TOKEN},
        timeout=30,
    )
    create_data = create_resp.json()
    if "id" not in create_data:
        raise RuntimeError(f"Instagram container creation failed: {create_data}")
    creation_id = create_data["id"]

    status = None
    for _ in range(10):
        status_resp = requests.get(
            f"https://graph.facebook.com/{config.GRAPH_API_VERSION}/{creation_id}",
            params={"fields": "status_code", "access_token": config.META_ACCESS_TOKEN},
            timeout=30,
        )
        status = status_resp.json().get("status_code")
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise RuntimeError(f"Instagram container processing failed: {status_resp.json()}")
        time.sleep(3)

    publish_resp = requests.post(
        f"{base}/media_publish",
        data={"creation_id": creation_id, "access_token": config.META_ACCESS_TOKEN},
        timeout=30,
    )
    publish_data = publish_resp.json()
    if "id" not in publish_data:
        raise RuntimeError(f"Instagram publish failed: {publish_data}")
    return publish_data["id"]
