# 🎯 Quick Reference Card

## Notion Database Setup

### New Property Required
```
Property Name: AI Enrichment
Type: Checkbox
Default: Unchecked
```

**How to use:**
- ☐ Unchecked = Post as-is (up to 25k chars)
- ☑️ Checked = AI enrichment enabled (OpenAI transforms to long-form)

---

## GitHub Secrets (Verify These)

### Already Configured (from fetch script)
- ✅ `OPENAI_API_KEY` - Your OpenAI API key
- ✅ `OPENAI_MODEL` - (Optional) Model name

### Existing Secrets (No Changes)
- ✅ `NOTION_TOKEN`
- ✅ `NOTION_DB_ID`
- ✅ `API_KEY`, `API_KEY_SECRET`
- ✅ `ACCESS_TOKEN`, `ACCESS_TOKEN_SECRET`

---

## Deployment Commands

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Test locally (optional)
python main.py

# 3. Deploy
git add .
git commit -m "feat: Add AI enrichment for 25k char posts"
git push origin main

# 4. Monitor
# Go to: GitHub → Actions → X Poster
```

---

## Code Changes at a Glance

### main.py
```python
# NEW: OpenAI client initialization
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# NEW: OAuth1 for X API v2 direct calls
oauth = OAuth1(API_KEY, client_secret=API_KEY_SECRET, ...)

# NEW: Read checkbox from Notion
should_enrich = get_prop_checkbox(page, "AI Enrichment")

# NEW: Conditional enrichment
if should_enrich:
    text = enrich_post(text)  # OpenAI magic ✨

# NEW: Post with 25k support
tweet_id = post_tweet_v2(text, reply_to_id)
```

### requirements.txt
```diff
+ requests-oauthlib==2.0.0
```

### .github/workflows/post.yml
```diff
+ OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
+ OPENAI_MODEL: ${{ secrets.OPENAI_MODEL }}
```

---

## Example Usage

### Regular Post (No Change)
```
Notion Entry:
  Tweet Content: "Check out my new blog post!"
  AI Enrichment: ☐ Unchecked
  Status: Scheduled

Result:
  Posts exactly: "Check out my new blog post!"
```

### AI-Enriched Post (New!)
```
Notion Entry:
  Tweet Content: "OpenAI releases GPT-5"
  AI Enrichment: ☑️ Checked
  Status: Scheduled

Result:
  OpenAI expands into ~3k char structured post with:
  - Engaging hook
  - Background context
  - Key implications
  - Technical insights
  - Practical takeaways
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "OpenAI client not initialized" | Add `OPENAI_API_KEY` to GitHub Secrets |
| "X API error 401" | Check Twitter API credentials |
| Posts still 280 chars | Upgrade X account to Premium |
| Enrichment fails | Check OpenAI quota, falls back to original text |

---

## Key Features Preserved

✅ Thread support (Thread Group ID, Thread Position)  
✅ Status tracking (Scheduled → Posted/Failed)  
✅ Error message logging  
✅ Tweet ID recording  
✅ Posted Time tracking  
✅ Duplicate content detection  
✅ Rate limiting (2s delays)  
✅ DST-aware scheduling  

---

## Cost Estimate

**OpenAI (gpt-4o-mini):**
- ~$0.0006 per enriched post
- ~$0.02/month (1 post/day)

**X API:** Free tier supported

**GitHub Actions:** No change (~2% of free tier)

---

## Success Indicators

After deployment, check logs for:
```
[INFO] AI Enrichment enabled for page abcd1234...
[INFO] Enriched content: 45 → 3247 chars
[INFO] Posted tweet 1234567890 (3247 chars)
[INFO] Posted [thread_id] -> 1234567890
```

---

## Support

**Logs:** GitHub → Actions → X Poster → View logs  
**Status:** Check Notion database for Status=Posted/Failed  
**X:** View your profile to see published posts  

---

**Ready to Go! 🚀**

Your system now supports premium long-form AI posts while maintaining full backwards compatibility.
