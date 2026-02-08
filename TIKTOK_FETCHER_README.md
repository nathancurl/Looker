# TikTok/ByteDance Job Fetcher

Custom fetcher for TikTok and ByteDance career pages.

## Overview

TikTok and ByteDance use custom React-based (Next.js) career portals that heavily rely on JavaScript rendering. This makes traditional web scraping challenging.

### Career Sites
- **TikTok**: https://careers.tiktok.com → redirects to https://lifeattiktok.com
- **TikTok Search**: https://lifeattiktok.com/search
- **ByteDance**: https://jobs.bytedance.com → redirects to https://joinbytedance.com
- **ByteDance Search**: https://joinbytedance.com/search

## Implementation Details

### API Investigation Results

After extensive investigation, the following was discovered:

1. **No Public API**: TikTok/ByteDance do not expose a public REST or GraphQL API for job listings
2. **Protected Endpoints**: API endpoints exist (e.g., `/api/search/position`) but require authentication/cookies
3. **JavaScript Rendering**: Job data is loaded via Next.js server-side rendering and client-side hydration
4. **Rate Limiting**: Aggressive rate limiting and bot detection (302 redirects, timeouts)

### Job ID Format

Job postings use 19-digit numeric IDs (e.g., `7531986763343300871`)

URL patterns:
- `https://lifeattiktok.com/search/7531986763343300871`
- `https://careers.tiktok.com/position/7531986763343300871`

### Data Sources

The fetcher attempts multiple strategies:

1. **Next.js Data Extraction** (`__NEXT_DATA__`): Parse embedded JSON in server-rendered pages
2. **HTML Pattern Matching**: Extract job IDs from URL patterns in HTML
3. **Selenium/Playwright** (optional): Full JavaScript rendering for dynamic content

## Usage

### Basic Configuration

```yaml
sources:
  - name: "TikTok New Grad"
    fetcher: "tiktok"
    config:
      company: "TikTok"
      keywords:
        - "new grad"
        - "graduate"
        - "early career"
        - "software engineer"
      use_selenium: false
      brand: "tiktok"
```

### ByteDance Configuration

```yaml
sources:
  - name: "ByteDance Engineering"
    fetcher: "bytedance"
    config:
      company: "ByteDance"
      keywords:
        - "engineer"
        - "new grad"
      use_selenium: false
```

### Configuration Options

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Display name for the source |
| `company` | string | No | Company name (defaults to "TikTok" or "ByteDance") |
| `keywords` | list | No | Keywords to filter job titles |
| `use_selenium` | boolean | No | Use Selenium for JavaScript rendering (default: false) |
| `brand` | string | No | "tiktok" or "bytedance" (TikTokFetcher only) |

## Selenium Setup (Recommended)

For best results, use Selenium to render JavaScript:

### Installation

```bash
# Install Selenium
pip install selenium

# Install ChromeDriver (macOS)
brew install --cask chromedriver

# Or download manually:
# https://chromedriver.chromium.org/
```

### Configuration with Selenium

```yaml
sources:
  - name: "TikTok Careers"
    fetcher: "tiktok"
    config:
      company: "TikTok"
      use_selenium: true  # Enable Selenium
      keywords:
        - "software engineer"
```

## Testing the Fetcher

### Test Script

```python
from fetchers.tiktok import TikTokFetcher, ByteDanceFetcher

# Test TikTok fetcher
config = {
    'name': 'TikTok Test',
    'company': 'TikTok',
    'keywords': ['software', 'engineer', 'new grad'],
    'use_selenium': False,
    'brand': 'tiktok'
}

fetcher = TikTokFetcher(config)
jobs = fetcher.safe_fetch()

print(f'Found {len(jobs)} jobs')
for job in jobs[:5]:
    print(f'- {job.title} | {job.location} | {job.url}')
```

### Run Test

```bash
cd /Users/ncurl/side-projects/job-notification-discord
python3 -c "
from fetchers.tiktok import TikTokFetcher

config = {
    'name': 'TikTok Careers',
    'company': 'TikTok',
    'keywords': ['software engineer'],
    'use_selenium': False
}

fetcher = TikTokFetcher(config)
jobs = fetcher.fetch()
print(f'Found {len(jobs)} jobs')
for job in jobs:
    print(f'{job.title} - {job.url}')
"
```

## Limitations & Challenges

### Current Limitations

1. **JavaScript Rendering Required**: The search pages are heavily JavaScript-dependent
   - **Solution**: Use `use_selenium: true` for full rendering

2. **Rate Limiting**: TikTok/ByteDance employ aggressive bot detection
   - Returns 302 redirects or timeouts for automated requests
   - **Mitigation**: Use realistic user agents, add delays between requests

3. **No Job Details**: Initial scraping only gets job IDs, not full details
   - Titles default to "Position {id}" without additional detail fetching
   - **Enhancement needed**: Implement detail page fetching for each job ID

4. **Authentication Protection**: API endpoints require cookies/auth tokens
   - Cannot use simple REST API calls
   - Must scrape rendered HTML

### Known Issues

- **Timeouts**: The site may timeout or return 302 redirects for automated requests
- **Empty Results**: Without Selenium, may return 0 jobs due to JavaScript rendering
- **Limited Metadata**: Job metadata (team, location, type) may not be available without detail fetching

## Recommended Approach

Given the challenges, here are three approaches in order of reliability:

### Option 1: Selenium (Most Reliable)

```yaml
use_selenium: true
```

**Pros**: Full JavaScript rendering, sees all content
**Cons**: Slower, requires ChromeDriver installation

### Option 2: Manual Job Board Aggregators

Use existing job aggregators that already scrape TikTok:
- SimplifyJobs (GitHub repo)
- NewGrad repositories
- RippleMatch

**Pros**: Already maintained, no scraping needed
**Cons**: May not have latest postings

### Option 3: Direct Application Links

If you have specific job IDs, create them manually:

```python
# Known new grad positions
job_ids = [
    "7531986763343300871",  # Frontend Software Engineer Graduate - 2026
    "7489012345678901234",  # Backend Engineer - New Grad
]

for jid in job_ids:
    url = f"https://lifeattiktok.com/search/{jid}"
    # Create Job object...
```

## Future Enhancements

### Job Detail Fetching

Implement detail page scraping for each job ID:

```python
def fetch_job_details(self, job_id: str) -> dict:
    """Fetch full job details from detail page."""
    url = f"{self._base_url}/search/{job_id}"
    # Scrape detail page for title, location, description, etc.
    pass
```

### API Reverse Engineering

If their API authentication can be reverse-engineered:

```python
# Hypothetical API call
def _fetch_via_api(self, keyword: str, limit: int = 20) -> list:
    url = "https://careers.tiktok.com/api/search/position"
    payload = {"keyword": keyword, "limit": limit, "offset": 0}
    # Add necessary auth headers/cookies
    resp = requests.post(url, json=payload, headers=auth_headers)
    return resp.json()
```

### Proxies & Rotation

To avoid rate limiting:

```python
# Use rotating proxies
proxies = ["http://proxy1:8000", "http://proxy2:8000"]
# Rotate user agents
# Add random delays
```

## Alternative Data Sources

If direct scraping proves too difficult:

1. **LinkedIn Jobs API**: TikTok posts jobs on LinkedIn
2. **Greenhouse/Lever**: Check if they use a third-party ATS
3. **RSS Feeds**: Some companies offer RSS/Atom feeds
4. **Job Aggregators**: Indeed, Glassdoor, etc. may have APIs

## Example Job Posting

Here's an example new grad position from TikTok:

**Title**: Frontend Software Engineer Graduate - (Global Live Platform) - 2026 Start (BS/MS)
**ID**: 7531986763343300871
**URL**: https://lifeattiktok.com/search/7531986763343300871
**Team**: Technology
**Type**: Full-time
**Program**: Graduate Program

## Support & Resources

- **TikTok Careers**: https://lifeattiktok.com
- **ByteDance Careers**: https://joinbytedance.com
- **Application Limit**: Max 2 positions per candidate
- **GitHub Issue**: Report issues at [your-repo]/issues

## Sources

- [Job Search](https://lifeattiktok.com/search)
- [TikTok Careers](https://lifeattiktok.com/)
- [ByteDance Careers](https://joinbytedance.com/)
- [Frontend Software Engineer Graduate - 2026 Start](https://lifeattiktok.com/search/7531986763343300871)
