#!/usr/bin/env python3
"""
AI Content Fetcher
Reads trusted AI RSS feeds, scores items, picks top 1, summarizes to ≤220 chars,
and creates a Notion row with Status=Scheduled for automated posting.
"""

import os
import sys
import json
import logging
import argparse
import time
import hashlib
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Set, Tuple
from urllib.parse import urlparse
from collections import Counter

import feedparser
import tldextract
import requests
from dateutil import parser as date_parser
from notion_client import Client

# Optional OpenAI integration
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# ----- Config -----
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DB_ID = os.getenv("NOTION_DB_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

RSS_FEEDS = [
    # Major AI Labs & Companies
    "https://openai.com/blog/rss.xml",  # OpenAI
    "https://blog.google/technology/ai/rss/",  # Google AI Blog
    "https://blog.research.google/feeds/posts/default",  # Google Research (replaces DeepMind)
    "https://www.microsoft.com/en-us/research/feed/",  # Microsoft Research
    "https://blogs.microsoft.com/ai/feed/",  # Microsoft AI Blog
    "https://huggingface.co/blog/feed.xml",  # Hugging Face
    "https://stability.ai/news?format=rss",  # Stability AI
    
    # Hardware & Cloud AI
    "https://developer.nvidia.com/blog/feed/",  # NVIDIA
    "https://aws.amazon.com/blogs/machine-learning/feed/",  # AWS ML Blog
    
    # Tech News & Analysis
    "https://techcrunch.com/tag/artificial-intelligence/feed/",  # TechCrunch AI
    "https://venturebeat.com/category/ai/feed/",  # VentureBeat AI
]

BOOST_KEYWORDS = [
    "AI", "GenAI", "LLM", "agents", "model", "inference",
    "NVIDIA", "OpenAI", "Anthropic", "Meta"
]

MAX_ARTICLE_AGE_HOURS = 48
RECENCY_BOOST_HOURS = 24
MAX_TWEET_LENGTH = 220
SUMMARY_MAX_CHARS = 220

# ----- Logging -----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ----- Data Models -----
class NewsItem:
    def __init__(
        self,
        title: str,
        link: str,
        published: datetime,
        source_domain: str,
        image_url: Optional[str] = None,
        summary: Optional[str] = None
    ):
        self.title = title
        self.link = link
        self.published = published
        self.source_domain = source_domain
        self.image_url = image_url
        self.summary = summary
        self.score = 0.0

    def __repr__(self):
        return f"<NewsItem '{self.title[:50]}...' from {self.source_domain} score={self.score:.2f}>"


# ----- RSS Parsing -----
def get_recent_notion_content(notion: Client, db_id: str, days: int = 7) -> Set[Tuple[str, str]]:
    """
    Query Notion for recent Posted/Scheduled/Failed entries to prevent duplicates.
    Returns set of (normalized_title, link) tuples.
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_iso = cutoff.replace(microsecond=0).isoformat().replace('+00:00', 'Z')
        
        # Query for entries from last N days
        results = notion.databases.query(
            database_id=db_id,
            filter={
                "or": [
                    {"property": "Status", "select": {"equals": "Posted"}},
                    {"property": "Status", "select": {"equals": "Scheduled"}},
                    {"property": "Status", "select": {"equals": "Failed"}},
                ],
                "and": [
                    {"property": "Scheduled Time", "date": {"after": cutoff_iso}}
                ]
            },
            page_size=100
        )
        
        seen_content = set()
        for page in results.get("results", []):
            # Extract title from Tweet Content property
            title_prop = page["properties"].get("Tweet Content", {})
            title_blocks = title_prop.get("title", [])
            if title_blocks:
                content = "".join(b.get("plain_text", "") for b in title_blocks)
                # Normalize: lowercase, strip, remove extra spaces
                normalized = " ".join(content.lower().strip().split())
                if normalized and not normalized.startswith("[error]"):
                    seen_content.add((normalized, ""))  # We only have content, not original link
        
        logger.info(f"Found {len(seen_content)} recent entries in Notion (last {days} days)")
        return seen_content
    
    except Exception as e:
        logger.warning(f"Failed to query recent Notion content: {e}")
        return set()


def normalize_title(title: str) -> str:
    """Normalize title for comparison."""
    return " ".join(title.lower().strip().split())


def title_similarity(title1: str, title2: str) -> float:
    """Calculate simple word overlap similarity between titles."""
    words1 = set(normalize_title(title1).split())
    words2 = set(normalize_title(title2).split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1 & words2
    union = words1 | words2
    
    return len(intersection) / len(union) if union else 0.0


def parse_feeds() -> List[NewsItem]:
    """
    Fetch and parse all RSS feeds, returning normalized NewsItem objects.
    Enhanced with:
    - Notion duplicate checking
    - Exponential backoff retries
    - Better deduplication
    """
    items = []
    seen = set()  # dedupe by (link, normalized_title)
    
    # Get recent Notion content to prevent duplicates
    notion_seen = set()
    if NOTION_TOKEN and NOTION_DB_ID:
        try:
            notion = Client(auth=NOTION_TOKEN)
            notion_seen = get_recent_notion_content(notion, NOTION_DB_ID, days=7)
        except Exception as e:
            logger.warning(f"Could not fetch Notion history: {e}")
    
    for feed_url in RSS_FEEDS:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"Fetching feed: {feed_url} (attempt {attempt + 1}/{max_retries})")
                response = requests.get(feed_url, timeout=15)
                response.raise_for_status()
                feed = feedparser.parse(response.content)
                
                if feed.bozo and not feed.entries:
                    logger.warning(f"Feed parsing issue for {feed_url}: {feed.bozo_exception}")
                    break  # Don't retry on parse errors
                
                for entry in feed.entries:
                    title = entry.get("title", "").strip()
                    link = entry.get("link", "").strip()
                    
                    if not title or not link:
                        continue
                    
                    # Normalize title for comparison
                    norm_title = normalize_title(title)
                    
                    # Dedupe by link and normalized title
                    dedupe_key = (link, norm_title)
                    if dedupe_key in seen:
                        continue
                    
                    # Check against recent Notion content
                    if any(title_similarity(norm_title, n[0]) > 0.7 for n in notion_seen):
                        logger.warning(f"Skipping duplicate from Notion history: {title[:60]}...")
                        continue
                    
                    seen.add(dedupe_key)
                    
                    # Parse published date
                    published_str = entry.get("published") or entry.get("updated")
                    if published_str:
                        try:
                            published = date_parser.parse(published_str)
                            # Make timezone-aware if naive
                            if published.tzinfo is None:
                                published = published.replace(tzinfo=timezone.utc)
                        except Exception:
                            published = datetime.now(timezone.utc)
                    else:
                        published = datetime.now(timezone.utc)
                    
                    # Extract domain
                    extracted = tldextract.extract(link)
                    source_domain = f"{extracted.domain}.{extracted.suffix}" if extracted.domain else "unknown"
                    
                    # Image URL (optional)
                    image_url = None
                    if "media_content" in entry and entry.media_content:
                        image_url = entry.media_content[0].get("url")
                    elif "media_thumbnail" in entry and entry.media_thumbnail:
                        image_url = entry.media_thumbnail[0].get("url")
                    elif "enclosures" in entry and entry.enclosures:
                        for enc in entry.enclosures:
                            if enc.get("type", "").startswith("image"):
                                image_url = enc.get("href")
                                break
                    
                    # Summary (for fallback)
                    summary = entry.get("summary", "")
                    
                    items.append(NewsItem(
                        title=title,
                        link=link,
                        published=published,
                        source_domain=source_domain,
                        image_url=image_url,
                        summary=summary
                    ))
                
                # Success - break retry loop
                break
                
            except requests.RequestException as e:
                logger.warning(f"Request error for {feed_url} (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    sleep_time = 5 * (2 ** attempt)  # Exponential backoff: 5s, 10s, 20s
                    logger.info(f"Retrying in {sleep_time}s...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"Failed to fetch {feed_url} after {max_retries} attempts")
            except Exception as e:
                logger.error(f"Unexpected error fetching feed {feed_url}: {e}")
                break  # Don't retry on unexpected errors
    
    logger.info(f"Parsed {len(items)} unique items from {len(RSS_FEEDS)} feeds")
    return items


# ----- Scoring -----
def score_items(items: List[NewsItem], notion_recent: Optional[Set[Tuple[str, str]]] = None) -> List[NewsItem]:
    """
    Score items based on recency, keyword matches, and source diversity.
    Enhanced with:
    - Source diversity penalties (prevent over-representation)
    - Stricter recency boost (<24h heavily favored)
    - Similarity check against recent Notion content
    Filter out items older than 48h.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=MAX_ARTICLE_AGE_HOURS)
    recent_boost_cutoff = now - timedelta(hours=RECENCY_BOOST_HOURS)
    
    # Count source distribution
    source_counter = Counter(item.source_domain for item in items)
    total_items = len(items)
    
    filtered_items = []
    
    for item in items:
        # Filter out old items
        if item.published < cutoff:
            continue
        
        score = 0.0
        
        # Enhanced recency boost with stricter penalties
        if item.published:
            age_h = (now - item.published).total_seconds() / 3600
            if 0 <= age_h <= 6:
                score += 15  # Super fresh (< 6h)
            elif age_h <= 12:
                score += 12  # Very fresh (6-12h)
            elif age_h <= 24:
                score += 8   # Fresh (12-24h)
            elif age_h <= 36:
                score += 3   # Recent (24-36h)
            elif age_h <= 48:
                score += 1   # Older (36-48h) - minimal boost
            else:
                score -= 100  # Too old
        
        # Keyword matching: +2 per keyword in title
        title_upper = item.title.upper()
        for keyword in BOOST_KEYWORDS:
            if keyword.upper() in title_upper:
                score += 2.0
        
        # Source diversity penalty: penalize over-represented sources
        source_freq = source_counter[item.source_domain] / total_items
        if source_freq > 0.5:  # If source has >50% of items
            penalty = (source_freq - 0.5) * 10  # Penalty scales with over-representation
            score -= penalty
            logger.debug(f"Applied diversity penalty -{penalty:.2f} to {item.source_domain}")
        elif source_freq > 0.3:  # Moderate over-representation
            penalty = (source_freq - 0.3) * 5
            score -= penalty
        
        # Check similarity with recent Notion content if provided
        if notion_recent:
            norm_title = normalize_title(item.title)
            for notion_title, _ in notion_recent:
                similarity = title_similarity(norm_title, notion_title)
                if similarity > 0.6:  # High similarity threshold
                    penalty = (similarity - 0.6) * 15  # Strong penalty for similar content
                    score -= penalty
                    logger.debug(f"Applied similarity penalty -{penalty:.2f} for '{item.title[:40]}...'")
                    break
        
        item.score = score
        filtered_items.append(item)
    
    # Sort by score descending
    filtered_items.sort(key=lambda x: x.score, reverse=True)
    
    logger.info(f"Scored and filtered to {len(filtered_items)} items (within {MAX_ARTICLE_AGE_HOURS}h)")
    
    # Log top 5 for debugging
    if filtered_items:
        logger.info("Top 5 scored items:")
        for i, item in enumerate(filtered_items[:5], 1):
            age_h = (now - item.published).total_seconds() / 3600
            logger.info(f"  {i}. [{item.score:.2f}] {item.title[:60]}... ({item.source_domain}, {age_h:.1f}h old)")
    
    return filtered_items


# ----- Summarization -----
def summarize_with_openai(title: str, link: str, domain: str) -> str:
    """Use OpenAI Chat Completions API v1 to generate a concise summary ≤220 chars."""
    if not OPENAI_AVAILABLE or not OPENAI_API_KEY:
        raise RuntimeError("OpenAI not available")
    
    # Initialize client - let OpenAI SDK handle environment
    client = OpenAI(api_key=OPENAI_API_KEY)
    sys_msg = (
        "You produce one-line, factual, neutral summaries (≤220 characters). "
        "No hashtags, emojis, quotes, @mentions, or markdown. "
        "End with '(domain)'."
    )
    user_msg = json.dumps({"title": title, "link": link, "domain": domain}, ensure_ascii=False)
    
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.2,
            max_tokens=120,
        )
        text = (resp.choices[0].message.content or "").strip().replace("\n", " ")
        
        # Hard cap + suffix enforcement
        if len(text) > SUMMARY_MAX_CHARS:
            text = text[: SUMMARY_MAX_CHARS - 1] + "…"
        if not text.endswith(f"({domain})"):
            suffix = f" ({domain})"
            base = text[: max(0, SUMMARY_MAX_CHARS - len(suffix))].rstrip(" .,-–—")
            text = base + suffix
        return text
    
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        raise


def summarize_fallback(item: NewsItem) -> str:
    """Fallback summarization using heuristic approach."""
    import re
    
    # Start with title
    summary = item.title
    
    # Try to extract a key sentence from summary if available
    if item.summary:
        # Remove HTML tags
        clean_summary = re.sub(r'<[^>]+>', '', item.summary)
        # Clean up whitespace
        clean_summary = re.sub(r'\s+', ' ', clean_summary).strip()
        
        sentences = clean_summary.split(". ")
        for sentence in sentences:
            sentence = sentence.strip()
            # Skip very short sentences
            if len(sentence) < 30:
                continue
            # Prefer sentences with AI keywords
            if any(kw.lower() in sentence.lower() for kw in BOOST_KEYWORDS):
                summary = sentence
                break
        else:
            # If no keyword match, use the first substantial sentence
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) >= 30:
                    summary = sentence
                    break
    
    # Add domain suffix
    domain_suffix = f" ({item.source_domain})"
    
    # Truncate if needed to fit domain
    max_summary_len = MAX_TWEET_LENGTH - len(domain_suffix)
    if len(summary) > max_summary_len:
        summary = summary[:max_summary_len - 3] + "..."
    
    summary = summary + domain_suffix
    
    return summary


def summarize_item(item: NewsItem) -> str:
    """Generate summary using OpenAI if available, otherwise fallback."""
    domain = item.source_domain or "news"
    title = item.title.strip()
    link = item.link.strip()
    
    if OPENAI_API_KEY:
        try:
            logger.info("Using OpenAI for summarization")
            return summarize_with_openai(title, link, domain)
        except Exception as e:
            logger.warning(f"OpenAI summarization failed, using fallback: {e}")
    
    logger.info("Using fallback summarization")
    return summarize_fallback(item)


def generate_long_form(short_summary: str) -> str:
    """Transform short summary into premium long-form post using OpenAI.
    
    Args:
        short_summary: Short summary text to expand
        
    Returns:
        Long-form premium post (2,000-5,000 chars target, max 25,000)
        Falls back to short_summary if OpenAI unavailable or fails
    """
    if not OPENAI_AVAILABLE:
        logger.error("❌ CRITICAL: OpenAI library not available (import failed)")
        logger.error("Install with: pip install openai")
        logger.error("Falling back to SHORT summary")
        return short_summary
    
    if not OPENAI_API_KEY:
        logger.error("❌ CRITICAL: OPENAI_API_KEY environment variable not set")
        logger.error("Long-form generation DISABLED - posts will be SHORT")
        logger.error("Set OPENAI_API_KEY in GitHub Secrets")
        return short_summary
    
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        system_prompt = """You are an expert AI content writer specializing in creating engaging, educational long-form posts about artificial intelligence and technology.

Your task: Transform short content into premium long-form posts (up to 25,000 characters) for X/Twitter Premium.

Style guidelines:
- Write in a clear, engaging, and educational tone for a general tech-savvy audience
- Use proper structure: headings (##), bullet points, short paragraphs
- Focus on insights, implications, and educational value
- Include relevant context and background
- Be conversational yet professional
- Break down complex concepts into digestible sections
- Add practical takeaways where relevant

Format:
- Start with a compelling hook or summary
- Use markdown formatting (##, -, *, etc.)
- Keep paragraphs short (2-4 sentences)
- Use bullet points for lists and key points
- End with a thought-provoking conclusion or call-to-action

Maximum length: 25,000 characters
Target: 2,000-5,000 characters for most posts (go longer if content warrants it)"""

        user_prompt = f"""Transform this content into a premium long-form post:

{short_summary}

Create an engaging, educational post that expands on this topic while maintaining the core message."""

        logger.info(f"🤖 Calling OpenAI {OPENAI_MODEL} to generate long-form content...")
        logger.info(f"Input: {len(short_summary)} chars → Target: 2,000-5,000 chars")
        
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=8000
        )
        
        enriched = response.choices[0].message.content.strip()
        
        # Ensure we don't exceed X's 25k limit
        if len(enriched) > 25000:
            logger.warning(f"Long-form content too long ({len(enriched)} chars). Truncating to 25k.")
            enriched = enriched[:24900] + "..."
        
        logger.info(f"✅ SUCCESS: Generated long-form content: {len(short_summary)} → {len(enriched)} chars")
        
        if len(enriched) < 500:
            logger.error(f"⚠️ WARNING: Long-form is suspiciously short ({len(enriched)} chars)")
            logger.error("OpenAI may not have understood the prompt correctly")
        
        return enriched
        
    except Exception as e:
        logger.error(f"❌ CRITICAL: Long-form generation failed: {e}")
        logger.error(f"Falling back to short summary ({len(short_summary)} chars)")
        logger.error("This means the post will be SHORT, not long-form!")
        return short_summary


# ----- Notion Integration -----
def notion_client() -> Client:
    """Create a Notion client instance."""
    if not NOTION_TOKEN:
        raise RuntimeError("NOTION_TOKEN must be set")
    return Client(auth=NOTION_TOKEN)


def notion_create_row(notion: Client, db_id: str, *, title: str,
                      scheduled_time: datetime, long_form_content: Optional[str] = None,
                      media_url: Optional[str] = None,
                      status: str = "Scheduled", error: Optional[str] = None):
    """Create a row in the Notion database."""
    properties = {
        "Tweet Content": {"title": [{"type": "text", "text": {"content": title}}]},
        "Scheduled Time": {"date": {"start": scheduled_time.replace(microsecond=0).isoformat().replace('+00:00', 'Z')}},
        "Status": {"select": {"name": status}},
    }
    if long_form_content:
        properties["Long Form Draft"] = {"rich_text": [{"type": "text", "text": {"content": long_form_content}}]}
    if media_url:
        properties["Media URLs"] = {"rich_text": [{"type": "text", "text": {"content": media_url}}]}
    if error:
        properties["Error Message"] = {"rich_text": [{"type": "text", "text": {"content": error[:1800]}}]}
    
    return notion.pages.create(parent={"database_id": db_id}, properties=properties)


def write_skipped_row():
    """Write a Skipped row to Notion when no fresh items are found."""
    try:
        notion = notion_client()
        db_id = os.environ["NOTION_DB_ID"]
        notion_create_row(
            notion, db_id,
            title="(No fresh AI news today.) (system)",
            scheduled_time=datetime.now(timezone.utc) - timedelta(minutes=5),
            status="Skipped",
        )
        logger.info("Wrote Skipped row to Notion.")
    except Exception as e:
        logger.error("Failed to write Skipped row: %s", e)


def create_notion_entry(long_form_content: str, item: NewsItem) -> bool:
    """Create a Notion database entry with Status=Scheduled.
    
    Saves pre-generated long-form content to Notion.
    """
    if not NOTION_TOKEN or not NOTION_DB_ID:
        raise RuntimeError("NOTION_TOKEN and NOTION_DB_ID must be set")
    
    scheduled_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    
    # Generate short title from item title (max 200 chars for Tweet Content field)
    title_content = item.title[:200] if len(item.title) <= 200 else f"{item.title[:197]}..."
    
    logger.info(f"Saving to Notion: {len(long_form_content)} character long-form post")
    logger.info(f"  Title: {title_content}")
    
    try:
        notion = notion_client()
        notion_create_row(
            notion, NOTION_DB_ID,
            title=title_content,  # Short title for table view
            long_form_content=long_form_content,  # Full content in Long Form Draft
            scheduled_time=scheduled_time,
            media_url=item.image_url,
            status="Scheduled",
        )
        logger.info(f"✅ Successfully saved long-form content ({len(long_form_content)} chars) to Notion")
        logger.info(f"   - Tweet Content (title): {len(title_content)} chars")
        logger.info(f"   - Long Form Draft: {len(long_form_content)} chars")
        return True
    except Exception as e:
        logger.error(f"Failed to create Notion entry: {e}")
        # Try to create error entry
        try:
            notion = notion_client()
            notion_create_row(
                notion, NOTION_DB_ID,
                title=f"[ERROR] Failed to create entry for: {item.title[:100]}",
                scheduled_time=scheduled_time,
                status="Failed",
                error=str(e),
            )
            logger.info("Created error entry in Notion")
        except Exception as e2:
            logger.error(f"Failed to create error entry: {e2}")
        return False


# ----- Main -----
def main():
    parser = argparse.ArgumentParser(description="AI Content Fetcher")
    parser.add_argument("--dry-run", action="store_true", help="Print summary without writing to Notion")
    args = parser.parse_args()
    
    logger.info("=== AI Content Fetcher Started ===")
    logger.info(f"Dry run mode: {args.dry_run}")
    
    try:
        # 1. Parse feeds (with Notion duplicate checking)
        items = parse_feeds()
        
        if not items:
            logger.warning("No items found in any feed")
            if not args.dry_run:
                write_skipped_row()
            return 0
        
        # Get recent Notion content for scoring
        notion_recent = set()
        if NOTION_TOKEN and NOTION_DB_ID:
            try:
                notion = notion_client()
                notion_recent = get_recent_notion_content(notion, NOTION_DB_ID, days=7)
            except Exception as e:
                logger.warning(f"Could not fetch Notion history for scoring: {e}")
        
        # 2. Score and filter with enhanced diversity and freshness checks
        scored_items = score_items(items, notion_recent=notion_recent)
        
        if not scored_items:
            logger.warning(f"No items within last {MAX_ARTICLE_AGE_HOURS}h")
            if args.dry_run:
                print("No fresh items (≤48h); Skipped.")
                return 0
            write_skipped_row()
            print("No fresh items (≤48h); Skipped.")
            return 0
        
        # 3. Pick top item
        top_item = scored_items[0]
        logger.info(f"Selected top item (score={top_item.score:.2f}): {top_item.title}")
        logger.info(f"  Link: {top_item.link}")
        logger.info(f"  Published: {top_item.published}")
        logger.info(f"  Source: {top_item.source_domain}")
        
        # 4. Summarize
        summary = summarize_item(top_item)
        logger.info(f"Generated short summary ({len(summary)} chars): {summary}")
        
        # 5. Generate long-form content (always, even in dry-run)
        logger.info("=" * 60)
        logger.info("STEP 5: GENERATING LONG-FORM CONTENT")
        logger.info("=" * 60)
        long_form_content = generate_long_form(summary)
        logger.info("=" * 60)
        logger.info(f"LONG-FORM READY: {len(long_form_content)} characters")
        logger.info("=" * 60)
        
        # 6. Dry-run output
        if args.dry_run:
            print(json.dumps({
                "short_summary": summary,
                "long_form_content": long_form_content,
                "long_form_length": len(long_form_content),
                "title": top_item.title,
                "link": top_item.link,
                "published": top_item.published.isoformat() if top_item.published else None,
                "image_url": top_item.image_url,
                "domain": top_item.source_domain,
                "note": "dry-run: Notion write skipped (long-form content generated above)"
            }, ensure_ascii=False, indent=2))
            return 0
        
        # 7. Create Notion entry with long-form content
        success = create_notion_entry(long_form_content, top_item)
        
        if success:
            logger.info("=== AI Content Fetcher Completed Successfully ===")
        else:
            logger.error("=== AI Content Fetcher Completed with Errors ===")
            sys.exit(1)
    
    except Exception as e:
        logger.exception("Fatal error in AI Content Fetcher")
        
        # Try to log error to Notion
        if not args.dry_run and NOTION_TOKEN and NOTION_DB_ID:
            try:
                notion = Client(auth=NOTION_TOKEN)
                scheduled_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
                notion_create_row(
                    notion, NOTION_DB_ID,
                    title="[ERROR] AI Content Fetcher failed",
                    scheduled_time=datetime.now(timezone.utc),
                    status="Failed",
                    error=str(e)
                )
            except:
                pass
        
        sys.exit(1)


if __name__ == "__main__":
    main()
