<div align="center">

# 🤖 Notion X Scheduler

### Automated AI News Curation & Social Media Publishing

[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-Automated-2088FF?style=for-the-badge&logo=github-actions&logoColor=white)](https://github.com/features/actions)
[![Notion](https://img.shields.io/badge/Notion-Database-000000?style=for-the-badge&logo=notion&logoColor=white)](https://notion.so)
[![Twitter/X](https://img.shields.io/badge/X-Posting-000000?style=for-the-badge&logo=x&logoColor=white)](https://x.com)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)

*Automatically fetch AI news from trusted sources, generate intelligent summaries, and schedule social media posts through Notion—all hands-free.*

[Features](#-features) • [Quick Start](#-quick-start) • [Configuration](#%EF%B8%8F-configuration) • [Architecture](#-architecture) • [Contributing](#-contributing)

---

</div>

## 🌟 Overview

**Notion X Scheduler** is a fully automated content curation and publishing system that:

1. **🔍 Discovers** - Scans 7+ trusted AI RSS feeds daily for breaking news
2. **🧠 Analyzes** - Scores articles using recency & keyword relevance algorithms  
3. **✍️ Summarizes** - Generates concise ≤220 char summaries via OpenAI GPT-4o-mini
4. **📝 Schedules** - Creates Notion database entries with `Status=Scheduled`
5. **📤 Publishes** - Automatically posts to X (Twitter) via existing workflow

<div align="center">

```mermaid
graph LR
    A[RSS Feeds] -->|Parse| B[AI Content Fetcher]
    B -->|Score & Rank| C[Top Article]
    C -->|Summarize| D[OpenAI GPT-4o-mini]
    D -->|Create Row| E[Notion Database]
    E -->|Status=Scheduled| F[X Poster]
    F -->|Publish| G[Twitter/X]
    
    style A fill:#4A90E2
    style B fill:#7B68EE
    style D fill:#10A37F
    style E fill:#000000,color:#fff
    style G fill:#1DA1F2
```

</div>

## ✨ Features

### 🤖 AI Content Fetcher

<table>
<tr>
<td width="50%">

**📡 Smart Feed Aggregation**
- OpenAI Blog
- HuggingFace Blog  
- Meta AI Research
- NVIDIA Developer Blog
- Anthropic News
- TechCrunch AI
- VentureBeat AI

</td>
<td width="50%">

**🎯 Intelligent Scoring**
- +10 points for articles <24h old
- +2 points per AI keyword match
- Smooth decay for 24-48h content
- Auto-filters content >48h old

</td>
</tr>
<tr>
<td>

**✨ AI-Powered Summaries**
- Uses OpenAI `gpt-4o-mini` by default
- Fallback to heuristic summarization
- ≤220 characters (X-optimized)
- Factual, no hashtags/emojis

</td>
<td>

**📊 Observability**
- Structured JSON dry-run output
- "Skipped" rows when no fresh content
- Error tracking in Notion
- Clean logging with timestamps

</td>
</tr>
</table>

### 📅 Automated Scheduling

- **Daily Runs**: 07:05 UTC (≈08:05 CET)
- **Manual Dispatch**: Run on-demand with dry-run option
- **Notion Integration**: Seamless database entry creation
- **X Posting**: Existing workflow handles publication

---

## 🚀 Quick Start

### Prerequisites

- GitHub account with Actions enabled
- Notion workspace with integration token
- X (Twitter) API credentials
- (Optional) OpenAI API key for enhanced summaries

### 1️⃣ Fork & Clone

```bash
git clone https://github.com/skalaliya/notion-x-scheduler.git
cd notion-x-scheduler
```

### 2️⃣ Set Up Notion Database

Create a Notion database with these exact properties:

| Property Name | Type | Options |
|--------------|------|---------|
| `Tweet Content` | Title | - |
| `Scheduled Time` | Date | Include time |
| `Status` | Select | Draft, Scheduled, Posted, Failed, Skipped |
| `Error Message` | Rich Text | - |
| `Tweet ID` | Text | - |
| `Media URLs` | Text | - |
| `Local Media` | Files & Media | - |

### 3️⃣ Configure Secrets

Go to **Settings → Secrets and variables → Actions** and add:

```yaml
Required:
  NOTION_TOKEN: "secret_xxxxxxxxxxxxx"
  NOTION_DB_ID: "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  API_KEY: "your_x_api_key"
  API_KEY_SECRET: "your_x_api_secret"
  ACCESS_TOKEN: "your_x_access_token"
  ACCESS_TOKEN_SECRET: "your_x_access_secret"

Optional:
  OPENAI_API_KEY: "sk-xxxxxxxxxxxxx"  # For AI summaries
  OPENAI_MODEL: "gpt-4o-mini"         # Override default model
```

### 4️⃣ Test the Workflow

**Dry Run (No Notion writes):**
```bash
python fetch_ai_news.py --dry-run
```

**Manual GitHub Actions Run:**
1. Go to **Actions** → **AI Content Fetcher**
2. Click **Run workflow**
3. Select `dry_run: true` for testing

### 5️⃣ Verify & Deploy

Check your Notion database for a new entry with:
- ✅ `Status = Scheduled`
- ✅ `Scheduled Time ≈ now - 5 minutes`
- ✅ `Tweet Content` ≤220 characters

The X posting workflow will automatically publish it!

---

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NOTION_TOKEN` | - | Notion integration token (required) |
| `NOTION_DB_ID` | - | Database ID from Notion URL (required) |
| `OPENAI_API_KEY` | - | OpenAI API key (optional, enables AI summaries) |
| `OPENAI_MODEL` | `gpt-4o-mini` | Override OpenAI model |
| `API_KEY` | - | X API key (required for posting) |
| `API_KEY_SECRET` | - | X API secret (required) |
| `ACCESS_TOKEN` | - | X access token (required) |
| `ACCESS_TOKEN_SECRET` | - | X access secret (required) |

### Workflow Schedules

**AI Content Fetcher** (`fetch.yml`):
- **Schedule**: Daily at 07:05 UTC
- **Timeout**: 10 minutes
- **Concurrency**: Cancels previous runs

**X Poster** (`post.yml`):
- **Schedule**: Every hour
- **Scope**: Posts with `Status=Scheduled` and past `Scheduled Time`

### Customization

**Modify RSS Feeds:**
Edit `fetch_ai_news.py` line 36-44:
```python
RSS_FEEDS = [
    "https://your-custom-feed.com/rss.xml",
    # Add more feeds...
]
```

**Adjust Scoring Keywords:**
Edit `fetch_ai_news.py` line 46-49:
```python
BOOST_KEYWORDS = [
    "AI", "GenAI", "LLM", "agents", "model",
    "YourKeyword",  # Add custom keywords
]
```

**Change Time Windows:**
```python
MAX_ARTICLE_AGE_HOURS = 48    # Filter older articles
RECENCY_BOOST_HOURS = 24      # Boost recent articles
SUMMARY_MAX_CHARS = 220       # Tweet length limit
```

---

## 🏗️ Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions Runner                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐         ┌──────────────────┐          │
│  │  fetch_ai_news.py│         │     main.py      │          │
│  │  (Daily 07:05)   │         │  (Hourly :00)    │          │
│  └────────┬─────────┘         └────────┬─────────┘          │
│           │                             │                     │
│           ▼                             ▼                     │
│  ┌─────────────────┐          ┌─────────────────┐           │
│  │  RSS Feeds      │          │ Notion Database │           │
│  │  - OpenAI       │◄─────────┤ Status Filter   │           │
│  │  - HuggingFace  │          └────────┬─────────┘           │
│  │  - Meta AI      │                   │                     │
│  │  - NVIDIA       │                   ▼                     │
│  │  - Anthropic    │          ┌─────────────────┐           │
│  │  - TechCrunch   │          │   X (Twitter)   │           │
│  │  - VentureBeat  │          │   API Client    │           │
│  └─────────────────┘          └─────────────────┘           │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

### Data Flow

```python
# 1. Fetch & Parse
feeds → feedparser → normalize(title, link, published, domain, image)

# 2. Score & Filter
items → filter(age <= 48h) → score(recency + keywords) → sort(desc) → top_item

# 3. Summarize
top_item → OpenAI(gpt-4o-mini) OR heuristic_fallback → summary (≤220 chars)

# 4. Schedule
summary → Notion.create_row(Status="Scheduled", Time=now-5m)

# 5. Publish (separate workflow)
Notion.query(Status="Scheduled", Time<=now) → X.post() → update(Status="Posted")
```

### File Structure

```
notion-x-scheduler/
├── .github/workflows/
│   ├── fetch.yml          # AI content fetcher (daily)
│   └── post.yml           # X poster (hourly)
├── fetch_ai_news.py       # Main fetcher script
├── main.py                # X posting script
├── requirements.txt       # Python dependencies
├── README.md              # This file
└── LICENSE                # MIT License
```

---

## 📊 Usage Examples

### Dry Run (Local Testing)

```bash
# No secrets required - uses fallback summarization
python fetch_ai_news.py --dry-run
```

**Output:**
```json
{
  "summary": "OpenAI announces GPT-5 with improved reasoning capabilities. (openai.com)",
  "title": "Introducing GPT-5: The Next Generation",
  "link": "https://openai.com/blog/gpt-5-announcement",
  "published": "2025-10-27T08:00:00+00:00",
  "image_url": "https://cdn.openai.com/gpt5-preview.jpg",
  "domain": "openai.com",
  "note": "dry-run: Notion write skipped"
}
```

### Manual GitHub Actions Run

**With Dry Run:**
1. Actions → AI Content Fetcher → Run workflow
2. Toggle `dry_run: true`
3. Check workflow logs for JSON output

**Production Run:**
1. Actions → AI Content Fetcher → Run workflow  
2. Keep `dry_run: false`
3. Check Notion database for new entry

### Skipped Content Example

When no articles are found within 48 hours:
- **Dry run**: Prints `"No fresh items (≤48h); Skipped."`
- **Production**: Creates Notion row with `Status=Skipped`

---

## 🔧 Troubleshooting

### Common Issues

**❌ "No module named 'feedparser'"**
```bash
pip install -r requirements.txt
```

**❌ "NOTION_TOKEN must be set"**
- Verify secret is added in GitHub Settings
- Check secret name spelling (case-sensitive)

**❌ "404 Client Error" for RSS feeds**
- Some feed URLs may change over time
- Update URLs in `RSS_FEEDS` list

**❌ "OpenAI API error: 401 Unauthorized"**
- Verify `OPENAI_API_KEY` is valid
- Script will fall back to heuristic summarization

**❌ "Can't compare offset-naive and offset-aware datetimes"**
- Already fixed in current version
- Ensure you're using the latest code

### Debug Mode

Enable verbose logging:
```python
logging.basicConfig(level=logging.DEBUG)
```

View workflow logs:
- Actions → Select workflow run → View logs

---

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

### Ideas for Enhancement

- [ ] Add more RSS feed sources
- [ ] Implement duplicate detection across days
- [ ] Add support for Twitter threads
- [ ] Create web dashboard for analytics
- [ ] Add webhook notifications (Discord, Slack)
- [ ] Implement A/B testing for summaries
- [ ] Add image generation for posts
- [ ] Support multiple languages

### How to Contribute

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Code Style

- Follow PEP 8 for Python code
- Add docstrings to functions
- Include type hints where applicable
- Write tests for new features

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **OpenAI** for GPT-4o-mini API
- **Notion** for the amazing database platform
- **X (Twitter)** for the API
- **GitHub Actions** for free automation
- RSS feed providers: OpenAI, HuggingFace, Meta, NVIDIA, Anthropic, TechCrunch, VentureBeat

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/skalaliya/notion-x-scheduler/issues)
- **Discussions**: [GitHub Discussions](https://github.com/skalaliya/notion-x-scheduler/discussions)
- **Twitter**: Share your setup with `#NotionXScheduler`

---

<div align="center">

### ⭐ Star this repo if it helped you!

**Made with ❤️ by [skalaliya](https://github.com/skalaliya)**

[![GitHub stars](https://img.shields.io/github/stars/skalaliya/notion-x-scheduler?style=social)](https://github.com/skalaliya/notion-x-scheduler)
[![GitHub forks](https://img.shields.io/github/forks/skalaliya/notion-x-scheduler?style=social)](https://github.com/skalaliya/notion-x-scheduler/fork)

</div>
