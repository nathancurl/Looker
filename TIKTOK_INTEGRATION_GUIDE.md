# TikTok/ByteDance Fetcher Integration Guide

Quick guide to integrate the TikTok/ByteDance fetchers into your job notification system.

## Quick Start

### 1. Files Created

- `/fetchers/tiktok.py` - Main fetcher implementation (TikTokFetcher & ByteDanceFetcher)
- `test_tiktok_fetcher.py` - Test suite
- `config_example_tiktok.yaml` - Configuration examples
- `TIKTOK_FETCHER_README.md` - Detailed usage documentation
- `TIKTOK_API_STRUCTURE.md` - API investigation findings

### 2. Add to Fetcher Registry

Edit your fetcher factory/loader to include the new fetchers:

```python
# In your main.py or fetcher_factory.py
from fetchers.tiktok import TikTokFetcher, ByteDanceFetcher

FETCHER_MAP = {
    "google": GoogleFetcher,
    "lever": LeverFetcher,
    # ... existing fetchers ...
    "tiktok": TikTokFetcher,      # Add this
    "bytedance": ByteDanceFetcher,  # Add this
}
```

### 3. Add Configuration

Add to your `sources.yaml` or configuration file:

```yaml
sources:
  - name: "TikTok New Grad"
    fetcher: "tiktok"
    enabled: true
    config:
      company: "TikTok"
      brand: "tiktok"
      keywords:
        - "new grad"
        - "graduate"
        - "software engineer"
      use_selenium: false  # Set true for better results

  - name: "ByteDance Engineering"
    fetcher: "bytedance"
    enabled: true
    config:
      company: "ByteDance"
      keywords:
        - "engineer"
        - "software"
      use_selenium: false
```

### 4. Test the Integration

```bash
# Run test suite
python3 test_tiktok_fetcher.py

# Test with your actual runner
python3 main.py --source "TikTok New Grad" --dry-run
```

## Installation Options

### Option A: Basic (No Selenium)

No additional dependencies needed. Works with standard `requests` library.

**Limitations**: May return 0 jobs due to JavaScript rendering.

```yaml
use_selenium: false
```

### Option B: With Selenium (Recommended)

Install Selenium and ChromeDriver:

```bash
# Install Selenium
pip install selenium

# macOS: Install ChromeDriver
brew install --cask chromedriver

# Linux: Download ChromeDriver
wget https://chromedriver.storage.googleapis.com/LATEST_RELEASE
# ... extract and add to PATH

# Windows: Download from
# https://chromedriver.chromium.org/
```

Update config:

```yaml
use_selenium: true
```

## Expected Behavior

### Without Selenium

```
Found 0 jobs
TikTok Careers: no jobs found. The page may be JavaScript-rendered.
Consider setting use_selenium=true in config for better results.
```

This is expected. The pages are JavaScript-heavy and require rendering.

### With Selenium

```
Found 15 jobs
1. Frontend Software Engineer Graduate - 2026 Start
   Location: San Jose, CA
   URL: https://lifeattiktok.com/search/7531986763343300871
...
```

Jobs are extracted after JavaScript rendering.

### Rate Limiting

```
WARNING: request timed out. The site may have bot detection.
Try using selenium or check rate limits.
```

If you see this:
1. Add delays between fetches (60+ seconds)
2. Use Selenium
3. Consider using proxies

## Troubleshooting

### Issue: "No jobs found"

**Cause**: JavaScript not rendered
**Solution**: Enable Selenium (`use_selenium: true`)

### Issue: "Request timed out"

**Cause**: Bot detection / rate limiting
**Solutions**:
- Increase timeout (already set to 30s in fetcher)
- Add delays between requests
- Use Selenium
- Use rotating proxies

### Issue: "302 Found" errors

**Cause**: Anti-bot protection
**Solutions**:
- Same as timeout issues
- Check if IP is blocked

### Issue: "Selenium not installed"

**Solution**:
```bash
pip install selenium
brew install --cask chromedriver  # macOS
```

### Issue: "ChromeDriver not found"

**Solution**:
```bash
# macOS
brew install --cask chromedriver

# Verify installation
which chromedriver
```

## Alternative Approaches

If the fetcher proves unreliable due to bot detection:

### 1. Use Job Aggregators

Already scraped by community repos:

```yaml
sources:
  - name: "SimplifyJobs GitHub"
    fetcher: "newgrad_json"
    config:
      github_repo: "SimplifyJobs/Summer2025-Internships"
      # TikTok jobs already included
```

### 2. Manual Job IDs

For specific roles, hardcode job IDs:

```python
from models import Job

known_tiktok_jobs = [
    ("7531986763343300871", "Frontend SWE Graduate - 2026", "San Jose, CA"),
    # Add more as you discover them
]

jobs = []
for job_id, title, location in known_tiktok_jobs:
    job = Job(
        uid=Job.generate_uid("tiktok", raw_id=f"tiktok:{job_id}"),
        source_group="tiktok",
        source_name="TikTok Manual",
        title=title,
        company="TikTok",
        location=location,
        url=f"https://lifeattiktok.com/search/{job_id}",
        raw_id=f"tiktok:{job_id}",
        snippet=""
    )
    jobs.append(job)
```

### 3. LinkedIn Integration

TikTok posts to LinkedIn. Use LinkedIn scraper if available.

## Performance Considerations

### Fetch Time

- **Without Selenium**: 1-5 seconds (may fail)
- **With Selenium**: 10-20 seconds (includes browser startup, rendering)

### Recommendations

1. **Cache Results**: Cache for 1-6 hours to avoid repeated fetches
2. **Background Jobs**: Run fetcher as background task
3. **Retry Logic**: Implement exponential backoff on failures
4. **Monitoring**: Track success rate and alert on failures

### Example Caching

```python
import time

last_fetch = {}
CACHE_TTL = 3600  # 1 hour

def fetch_with_cache(source_name, fetcher):
    now = time.time()
    if source_name in last_fetch:
        last_time, last_jobs = last_fetch[source_name]
        if now - last_time < CACHE_TTL:
            return last_jobs  # Return cached

    # Fetch fresh data
    jobs = fetcher.fetch()
    last_fetch[source_name] = (now, jobs)
    return jobs
```

## Integration with Discord Notifications

Example Discord webhook integration:

```python
import requests

def notify_discord(jobs, webhook_url):
    for job in jobs:
        embed = {
            "title": job.title,
            "description": job.snippet[:200],
            "url": job.url,
            "color": 0xFF0050,  # TikTok pink
            "fields": [
                {"name": "Company", "value": job.company, "inline": True},
                {"name": "Location", "value": job.location, "inline": True},
            ],
            "footer": {"text": f"Source: {job.source_name}"}
        }

        payload = {"embeds": [embed]}
        requests.post(webhook_url, json=payload)
```

## Monitoring & Alerts

Track fetcher health:

```python
import logging

logger = logging.getLogger(__name__)

def monitor_fetch_results(source_name, jobs, expected_min=5):
    if len(jobs) == 0:
        logger.warning(
            f"{source_name}: No jobs found. Check for rate limiting or page changes."
        )
        # Send alert to monitoring system
        alert_ops(f"{source_name} returned 0 jobs")

    elif len(jobs) < expected_min:
        logger.info(
            f"{source_name}: Only {len(jobs)} jobs found (expected >= {expected_min})"
        )

    else:
        logger.info(f"{source_name}: Successfully fetched {len(jobs)} jobs")
```

## Next Steps

1. Test the fetcher: `python3 test_tiktok_fetcher.py`
2. Review documentation: `TIKTOK_FETCHER_README.md`
3. Add to your config: Use `config_example_tiktok.yaml` as template
4. Monitor performance: Track success rate over first week
5. Adjust as needed: Enable Selenium, adjust keywords, add delays

## Questions?

See the full documentation:
- **Usage**: `TIKTOK_FETCHER_README.md`
- **API Details**: `TIKTOK_API_STRUCTURE.md`
- **Testing**: `test_tiktok_fetcher.py`

For issues, check logs and try:
1. Enable Selenium
2. Increase delays
3. Use job aggregators as fallback
