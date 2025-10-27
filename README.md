<h1 align="center">🧠 Notion-X Scheduler</h1>
<p align="center">
  <i>Daily AI news → summarized → queued in Notion → posted to X (Twitter) — fully automated.</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-v1.0.0-blue?style=for-the-badge"/>
  <img src="https://img.shields.io/github/actions/workflow/status/skalaliya/notion-x-scheduler/fetch.yml?label=AI%20Fetcher&style=for-the-badge"/>
  <img src="https://img.shields.io/github/actions/workflow/status/skalaliya/notion-x-scheduler/post.yml?label=X%20Poster&style=for-the-badge"/>
  <img src="https://img.shields.io/badge/OpenAI-gpt--4o--mini-2ea44f?style=for-the-badge&logo=openai"/>
  <img src="https://img.shields.io/badge/Notion-API-black?style=for-the-badge&logo=notion"/>
  <img src="https://img.shields.io/badge/Python-3.11-yellow?style=for-the-badge&logo=python"/>
</p>

---

## Overview

This repo automatically curates and posts AI news to X (Twitter) using a smart two-stage pipeline:

1. **Fetcher** runs daily at ~10:05 AM Europe/Paris time (DST-aware), parses 7 trusted AI RSS feeds, scores articles by relevance and recency, summarizes the top pick with OpenAI's `gpt-4o-mini`, and queues it in your Notion database with `Status=Scheduled`.

2. **Poster** triggers immediately after a successful fetch (plus hourly backup), checks Notion for ready posts (`Scheduled Time <= now`), and publishes them to X with proper thread support.

**Built and maintained by:** @skalaliya

---

## Architecture

```mermaid
graph TD
    A[AI RSS Feeds] --> B[fetch_ai_news.py]
    B -->|Summarize with gpt-4o-mini| C[Notion DB]
    C -->|Status=Scheduled & Time ready| D[X Poster]
    D -->|X API| E[Tweet Published 🚀]
```

---

## Features

* 📰 **Multi-source AI feeds** (OpenAI, Google AI, DeepMind, NVIDIA, AWS ML, TechCrunch, VentureBeat)
* 🧠 **Smart summarization** with `gpt-4o-mini` (cost-effective, high-quality) — graceful fallback to heuristics
* 🗂️ **Notion as content queue** (`Status=Scheduled` + `Scheduled Time` properties)
* ⏰ **DST-aware scheduling**: Runs at ~10:05 AM Paris time year-round (dual UTC crons)
* 🔁 **Event-chained workflows**: Poster auto-triggers after successful fetch (hourly backup)
* 🛡️ **Pre-check validation**: Skips poster run if no ready posts exist
* � **Dry-run mode**: Test with `--dry-run` flag or workflow dispatch for JSON output
* 🎯 **Relevance scoring**: Keyword matching + recency decay (48h window)

---

## Quick Start

### 1. Setup Secrets

Navigate to **GitHub → Settings → Secrets → Actions** and add:

**Required:**
* `NOTION_TOKEN` - Your Notion integration token
* `NOTION_DB_ID` - Target database ID
* `ACCESS_TOKEN`, `ACCESS_TOKEN_SECRET` - X/Twitter OAuth tokens
* `API_KEY`, `API_KEY_SECRET` - X/Twitter API credentials

**Optional:**
* `OPENAI_API_KEY` - Enables AI summarization (without it, uses heuristic fallback)
* `OPENAI_MODEL` - Override model (default: `gpt-4o-mini`)

### 2. Test Locally (Dry Run)

```bash
python fetch_ai_news.py --dry-run
```

Expected output: JSON with top article details or "No fresh items (≤48h); Skipped."

### 3. Run in Production

**Option A: Manual trigger**
* Go to **Actions → AI Content Fetcher → Run workflow**
* Set `dry_run=false`
* Click **Run**

**Option B: Automatic schedule**
* Fetcher runs daily at ~10:05 AM Europe/Paris time
* Poster triggers automatically after successful fetch

### 4. Monitor Execution

* **Fetcher**: Creates 1 `Status=Scheduled` row in Notion per run (if news found)
* **Poster**: Publishes scheduled posts and updates their status
* Check **Actions** tab for workflow logs and status

---

## How It Works

### Scheduling (DST-Aware)

The fetcher uses **dual UTC cron schedules** to maintain consistent Paris local time:

* **Mar–Oct (CEST, UTC+2)**: `5 8 * 3-10 *` → 08:05 UTC = 10:05 Paris
* **Nov–Feb (CET, UTC+1)**: `5 9 * 11-2 *` → 09:05 UTC = 10:05 Paris

GitHub Actions only supports UTC cron, so this dual-schedule approach automatically handles daylight saving transitions.

### Workflow Chain

```
Daily at 10:05 Paris
       ↓
[AI Content Fetcher]
       ↓ (on success)
[X Poster] ← also runs hourly as backup
       ↓
[check_ready_to_post.py validates Notion]
       ↓ (if posts ready)
[main.py publishes to X]
```

### Files

* **`fetch_ai_news.py`** (445 lines) - RSS parser, scorer, OpenAI integration, Notion writer
* **`main.py`** - X/Twitter poster with thread support
* **`check_ready_to_post.py`** - Pre-check validation script
* **`.github/workflows/fetch.yml`** - Fetcher workflow (Paris timezone scheduling)
* **`.github/workflows/post.yml`** - Poster workflow (event-chained + hourly backup)

---

## Costs (typical)

| Service              | Monthly | Notes                |
| -------------------- | ------: | -------------------- |
| GitHub Actions       |  ~$0.50 | ~60 min runtime      |
| OpenAI `gpt-4o-mini` |  <$0.01 | ~1 short summary/day |
| Notion API           |    Free | Included in plan     |

---

## Testing Matrix

* **LLM disabled:** Remove `OPENAI_API_KEY` → heuristic summaries activate automatically
* **Model override:** Set `OPENAI_MODEL` secret to test different models (e.g., `gpt-4`, `gpt-3.5-turbo`)
* **No news scenario:** Fetcher writes a "Skipped" row to Notion (production) or prints message (dry-run)
* **Manual dispatch:** Test anytime via Actions tab with `dry_run` toggle
* **Event-chain validation:** After manual fetch, verify poster auto-triggers within seconds

---

## Project Structure

```
notion-x-scheduler/
├── fetch_ai_news.py          # AI news fetcher (RSS → scoring → summarize → Notion)
├── main.py                   # X/Twitter poster (Notion → X API)
├── check_ready_to_post.py    # Pre-check validation for poster
├── requirements.txt          # Python dependencies
├── .github/workflows/
│   ├── fetch.yml            # Daily at 10:05 Paris (DST-aware)
│   └── post.yml             # Event-chained + hourly backup
└── README.md                # This file
```

---

## Contributing

PRs and issues welcome. If this helped, please ⭐ the repo:
**[https://github.com/skalaliya/notion-x-scheduler](https://github.com/skalaliya/notion-x-scheduler)**

---

## License

MIT
