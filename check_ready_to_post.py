import os
import sys
from datetime import datetime, timezone
from notion_client import Client

def has_ready_posts():
    notion = Client(auth=os.environ["NOTION_TOKEN"])
    db_id = os.environ["NOTION_DB_ID"]
    # Use ISO format with 'Z' suffix for Notion API
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')

    query = notion.databases.query(
        database_id=db_id,
        filter={
            "and": [
                {"property": "Status", "select": {"equals": "Scheduled"}},
                {"property": "Scheduled Time", "date": {"before": now}},
            ]
        },
        page_size=1,
    )
    return len(query.get("results", [])) > 0

if __name__ == "__main__":
    if has_ready_posts():
        print("✅ Ready posts found — continuing to X posting.")
        sys.exit(0)
    else:
        print("⚠️ No posts ready — exiting cleanly.")
        sys.exit(1)
