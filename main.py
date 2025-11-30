import os
import time
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import requests
from requests_oauthlib import OAuth1
from notion_client import Client

# ----- Config -----
UTC_NOW = datetime.now(timezone.utc)

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DB_ID = os.getenv("NOTION_DB_ID")

API_KEY = os.getenv("API_KEY")
API_KEY_SECRET = os.getenv("API_KEY_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")

# ----- Logging -----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ----- Clients -----
notion = Client(auth=NOTION_TOKEN)

# OAuth1 for direct X API v2 calls (supports 25k char tweets)
oauth = OAuth1(
    API_KEY,
    client_secret=API_KEY_SECRET,
    resource_owner_key=ACCESS_TOKEN,
    resource_owner_secret=ACCESS_TOKEN_SECRET
)

# ----- Helpers -----
def iso(dt_obj: datetime) -> str:
    """Convert datetime to ISO 8601 string with 'Z' suffix (UTC)."""
    # Convert to UTC explicitly, remove microseconds
    dt_obj = dt_obj.astimezone(timezone.utc)
    return dt_obj.replace(microsecond=0).isoformat().replace('+00:00', 'Z')

def notion_query_scheduled(db_id: str) -> List[Dict[str, Any]]:
    """
    Fetch pages where Status = Scheduled and Scheduled Time <= now (UTC).
    """
    return notion.databases.query(
        database_id=db_id,
        filter={
            "and": [
                {"property": "Status", "select": {"equals": "Scheduled"}},
                {"property": "Scheduled Time", "date": {"before": iso(UTC_NOW)}},
            ]
        },
        sorts=[{"property": "Scheduled Time", "direction": "ascending"}],
    )["results"]

def get_prop_text(p: Dict[str, Any], name: str) -> str:
    val = p["properties"].get(name)
    if not val:
        return ""
    # Title or Rich text
    blocks = val.get("title") or val.get("rich_text") or []
    return "".join(chunk.get("plain_text", "") for chunk in blocks)

def get_prop_number(p: Dict[str, Any], name: str) -> int:
    v = p["properties"].get(name, {}).get("number")
    return int(v) if v is not None else 0

def get_media_urls(p: Dict[str, Any]) -> List[str]:
    txt = get_prop_text(p, "Media URLs")
    urls = [u.strip() for u in txt.split() if u.strip().startswith("http")]
    return urls

def update_success(page_id: str, tweet_id: str):
    notion.pages.update(
        page_id,
        properties={
            "Status": {"select": {"name": "Posted"}},
            "Posted Time": {"date": {"start": iso(UTC_NOW)}},
            "Tweet ID": {"rich_text": [{"text": {"content": tweet_id}}]},
            "Error Message": {"rich_text": []},
        },
    )

def update_failure(page_id: str, error_msg: str):
    notion.pages.update(
        page_id,
        properties={
            "Status": {"select": {"name": "Failed"}},
            "Error Message": {"rich_text": [{"text": {"content": error_msg[:1800]}}]},
        },
    )

def post_tweet_v2(text: str, reply_to_id: Optional[str] = None) -> str:
    """
    Post tweet using X API v2 directly with OAuth1.
    Supports up to 25,000 characters for Premium accounts.
    
    Args:
        text: Tweet content (up to 25k chars)
        reply_to_id: Optional tweet ID to reply to (for threads)
        
    Returns:
        Tweet ID of posted tweet
    """
    url = "https://api.twitter.com/2/tweets"
    
    payload = {"text": text}
    if reply_to_id:
        payload["reply"] = {"in_reply_to_tweet_id": reply_to_id}
    
    response = requests.post(
        url,
        auth=oauth,
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code in [200, 201]:
        data = response.json()
        tweet_id = data["data"]["id"]
        logger.info(f"Posted tweet {tweet_id} ({len(text)} chars)")
        return tweet_id
    else:
        error_msg = f"X API error {response.status_code}: {response.text}"
        logger.error(error_msg)
        raise Exception(error_msg)

def run():
    if not all([NOTION_TOKEN, NOTION_DB_ID, API_KEY, API_KEY_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET]):
        raise RuntimeError("Missing one or more env vars / secrets")

    pages = notion_query_scheduled(NOTION_DB_ID)
    if not pages:
        logger.info("No scheduled posts due.")
        return

    logger.info(f"Found {len(pages)} post(s) due.")

    # Group by Thread Group ID (if present)
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for p in pages:
        props = p["properties"]
        group_id = get_prop_text(p, "Thread Group ID") or p["id"]  # default to page id
        groups.setdefault(group_id, []).append(p)

    for gid, items in groups.items():
        # Sort inside thread by Thread Position
        items.sort(key=lambda x: get_prop_number(x, "Thread Position") or 0)

        reply_to_id = None
        for page in items:
            page_id = page["id"]
            text = get_prop_text(page, "Tweet Content").strip()
            media_urls = get_media_urls(page)

            if not text:
                update_failure(page_id, "Empty Tweet Content")
                continue

            # Log content length for verification
            logger.info(f"Preparing to post content: {len(text)} characters")
            if len(text) < 500:
                logger.warning(f"⚠️ Content is suspiciously short ({len(text)} chars) - expected 2000-5000 chars for long-form")
            elif len(text) >= 2000:
                logger.info(f"✅ Long-form content detected ({len(text)} chars)")

            try:
                # Post content as-is (already enriched by fetch script)
                tweet_id = post_tweet_v2(text, reply_to_id)

                update_success(page_id, tweet_id)
                reply_to_id = tweet_id
                logger.info(f"Posted [{gid}] -> {tweet_id}")

                # polite pacing to avoid hitting minor limits
                time.sleep(2)
            except Exception as e:
                error_msg = str(e)
                logger.exception("Error during posting")
                
                # Check for duplicate content
                if "duplicate" in error_msg.lower():
                    logger.warning(f"Duplicate content detected for page {page_id[:8]}...")
                
                update_failure(page_id, error_msg[:1800])

if __name__ == "__main__":
    run()