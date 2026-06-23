import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

DEFAULT_XQUIK_API_BASE = "https://xquik.com/api/v1"


def build_xquik_payload(
    account: str,
    text: str,
    reply_to_id: Optional[str] = None,
) -> Dict[str, str]:
    payload = {"account": account, "text": text}
    if reply_to_id:
        payload["reply_to_tweet_id"] = reply_to_id
    return payload


def extract_xquik_identifier(body: Dict[str, Any]) -> str:
    for key in ("tweetId", "id", "writeActionId"):
        value = body.get(key)
        if value:
            return str(value)

    data = body.get("data")
    if isinstance(data, dict):
        for key in ("tweetId", "id", "writeActionId"):
            value = data.get(key)
            if value:
                return str(value)

    return "accepted"


def post_xquik_tweet(
    *,
    api_key: str,
    account: str,
    text: str,
    api_base: str = DEFAULT_XQUIK_API_BASE,
    reply_to_id: Optional[str] = None,
    timeout: int = 30,
) -> str:
    payload = build_xquik_payload(account, text, reply_to_id)
    request = urllib.request.Request(
        f"{api_base.rstrip('/')}/x/tweets",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status_code = response.status
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Xquik post failed with HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Xquik post failed: {error.reason}") from error

    if status_code not in (200, 202):
        raise RuntimeError(f"Xquik post failed with HTTP {status_code}: {response_body[:500]}")

    body = json.loads(response_body) if response_body else {}
    return extract_xquik_identifier(body)
