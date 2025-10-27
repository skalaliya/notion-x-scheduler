# notion-x-scheduler
Automated X (Twitter) posting from Notion using GitHub Actions + X API

## Features

### X (Twitter) Posting
The main posting workflow (`main.py`) reads scheduled posts from a Notion database and publishes them to X (Twitter) automatically. Posts with `Status=Scheduled` and a past `Scheduled Time` are picked up and posted.

### AI Content Fetcher
The AI Content Fetcher (`fetch_ai_news.py`) automatically discovers and curates AI news from trusted sources:

**What it does:**
- Fetches articles from 7 trusted AI RSS feeds (OpenAI, HuggingFace, Meta AI, NVIDIA, Anthropic, TechCrunch, VentureBeat)
- Scores articles based on recency (last 24h boost) and AI-related keywords
- Filters out articles older than 48 hours
- Selects the top article and summarizes it to ≤220 characters
- Creates a Notion database entry with `Status=Scheduled` for automatic posting
- Uses OpenAI API for summarization if `OPENAI_API_KEY` is provided, otherwise uses a heuristic fallback

**How to run manually:**
1. Go to **Actions** → **AI Content Fetcher** in your GitHub repository
2. Click **Run workflow**
3. Choose whether to enable **dry_run** mode:
   - `true`: Prints the selected article and summary without writing to Notion (for testing)
   - `false`: Creates the actual Notion entry

**Scheduled runs:**
The fetcher runs automatically every day at **07:05 UTC** (approximately 08:05 Paris time).

**Required secrets:**
- `NOTION_TOKEN`: Your Notion integration token
- `NOTION_DB_ID`: The ID of your Notion database
- `OPENAI_API_KEY`: (Optional) OpenAI API key for enhanced summarization

**Integration with posting:**
The fetcher creates Notion entries with `Status=Scheduled` and `Scheduled Time` set to 5 minutes before the current time. This makes the entries immediately available for the existing X posting workflow to pick up and publish automatically.
