import os, time, logging, datetime as dt
from typing import List, Dict, Any

import tweepy
from notion_client import Client

# ----- Config -----
UTC_NOW = dt.datetime.utcnow()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DB_ID = os.getenv("NOTION_DB_ID")

API_KEY = os.getenv("API_KEY")
API_KEY_SECRET = os.getenv("API_KEY_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")

# ----- Logging -----
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# ----- Clients -----
notion = Client(auth=NOTION_TOKEN)

twitter = tweepy.Client(
    consumer_key=API_KEY,
    consumer_secret=API_KEY_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET
)

# ----- Helpers -----
def iso(dt_obj: dt.datetime) -> str:
    return dt_obj.replace(microsecond=0).isoformat() + "Z"

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

def post_single_tweet(text: str, media_urls: List[str]) -> str:
    """
    Uses Twitter v2 API via Tweepy Client.create_tweet.
    Note: Media upload still requires v1.1 API if needed.
    """
    response = twitter.create_tweet(text=text)
    return str(response.data['id'])

def run():
    if not all([NOTION_TOKEN, NOTION_DB_ID, API_KEY, API_KEY_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET]):
        raise RuntimeError("Missing one or more env vars / secrets")

    pages = notion_query_scheduled(NOTION_DB_ID)
    if not pages:
        logging.info("No scheduled posts due.")
        return

    logging.info(f"Found {len(pages)} post(s) due.")

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

            try:
                # Basic: single text tweet. If thread position > 1, reply.
                if reply_to_id:
                    response = twitter.create_tweet(
                        text=text, 
                        in_reply_to_tweet_id=reply_to_id
                    )
                    tweet_id = str(response.data['id'])
                else:
                    tweet_id = post_single_tweet(text, media_urls)

                update_success(page_id, tweet_id)
                reply_to_id = tweet_id
                logging.info(f"Posted [{gid}] -> {tweet_id}")

                # polite pacing to avoid hitting minor limits
                time.sleep(2)
            except Exception as e:
                logging.exception("Posting failed")
                update_failure(page_id, str(e))

if __name__ == "__main__":
    run()