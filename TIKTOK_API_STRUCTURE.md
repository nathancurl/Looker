# TikTok/ByteDance API Structure Documentation

This document details the findings from investigating TikTok and ByteDance career site APIs.

## Executive Summary

**Finding**: TikTok/ByteDance do not expose a public API for job listings. The career portals use protected APIs that require authentication, and job data is primarily loaded via JavaScript (Next.js).

**Recommendation**: Use Selenium/Playwright for web scraping or leverage existing job aggregators.

---

## Career Site URLs

### TikTok
- **Primary**: https://careers.tiktok.com (302 redirect)
- **Redirect Target**: https://lifeattiktok.com
- **Search Page**: https://lifeattiktok.com/search
- **Job Detail**: https://lifeattiktok.com/search/{job_id}

### ByteDance
- **Primary**: https://jobs.bytedance.com (302 redirect)
- **Redirect Target**: https://joinbytedance.com
- **Search Page**: https://joinbytedance.com/search
- **Job Detail**: https://joinbytedance.com/search/{job_id}

---

## API Investigation Results

### Attempted Endpoints

All of the following endpoints were tested and found to be inaccessible:

1. `POST https://careers.tiktok.com/api/v1/search/job`
   - Response: 302 Found
   - Status: Protected

2. `POST https://careers.tiktok.com/api/search/position`
   - Response: 302 Found
   - Status: Protected

3. `POST https://careers.tiktok.com/api/portal/position/search`
   - Response: 302 Found
   - Status: Protected

4. `GET https://careers.tiktok.com/api/v1/position/list`
   - Response: 302 Found
   - Status: Protected

5. `GET https://careers.tiktok.com/feed.xml`
   - Response: HTML page (not RSS)
   - Status: No RSS feed available

6. `GET https://api.lever.co/v0/postings/tiktok?mode=json`
   - Response: {"ok": false, "error": "Document not found"}
   - Status: Not using Lever ATS

7. `GET https://api.lever.co/v0/postings/bytedance?mode=json`
   - Response: {"ok": false, "error": "Document not found"}
   - Status: Not using Lever ATS

### Authentication Requirements

The API endpoints return **302 Found** redirects, indicating:
- Bot detection / rate limiting
- Cookie/session requirements
- CSRF token requirements
- Cloudflare or similar protection

### Sample Request Patterns

```bash
# Attempted POST request
curl -X POST "https://careers.tiktok.com/api/search/position" \
  -H "Content-Type: application/json" \
  -H "User-Agent: Mozilla/5.0" \
  --data '{"keyword":"software engineer","limit":10,"offset":0}'
# Result: 302 Found
```

---

## Page Structure

### Technology Stack

- **Framework**: Next.js (React-based)
- **Rendering**: Server-side rendering (SSR) + Client-side hydration
- **Data Format**: JSON embedded in HTML
- **Analytics**: StackAdapt pixel tracking

### Data Embedding

#### 1. __NEXT_DATA__ (Standard Next.js)

Not consistently present. Some pages use streaming format instead.

```html
<script id="__NEXT_DATA__" type="application/json">
{
  "props": {
    "pageProps": {
      "jobs": [...]
    }
  }
}
</script>
```

#### 2. __next_f Streaming Format

Next.js uses a streaming format for progressive hydration:

```javascript
self.__next_f.push([1,"chunk_data"])
```

This format is harder to parse and requires extracting serialized React components.

#### 3. Job Configuration

Embedded configuration found in HTML:

```json
{
  "jobCommonSettings": {
    "applyJobWebsite": "https://careers.tiktok.com/resume/{id}/apply"
  }
}
```

---

## Job Data Structure

### Job ID Format

- **Format**: 19-digit numeric string
- **Example**: `7531986763343300871`
- **Pattern**: Starts with 7, appears to be a timestamp-based ID

### Job Fields (Inferred)

Based on page configuration and HTML patterns:

```json
{
  "id": "7531986763343300871",
  "title": "Frontend Software Engineer Graduate - 2026 Start",
  "job_category": "Technology",
  "job_category_id": "...",
  "recruit_type": "Full-time",
  "job_subject": "Graduate Program",
  "subject_id": "...",
  "location": {
    "city": "San Jose",
    "state": "CA",
    "country": "US",
    "city_info": "San Jose, CA",
    "location_code": "..."
  },
  "description": "...",
  "requirement": "...",
  "url": "https://lifeattiktok.com/search/7531986763343300871"
}
```

### Job Categories

From HTML meta configuration:

- Advertising & Sales
- Design
- Corporate Functions
- Global Operations
- Marketing & Communications
- Product
- **Technology** (primary target for engineering roles)

### Recruit Types

- Full-time
- Intern
- Contract
- Part-time

### Programs

- Graduate Program
- MBA/PhD Internship Program
- Early Career

---

## Search Filters

### Available Filters

1. **Keyword**: Free text search
2. **Job Type**: recruit_type values
3. **Job Category**: Team/department
4. **Program**: Special programs (intern, grad, etc.)
5. **Location**: By city/country code

### Search Parameters

```
GET /search?keyword={query}&location_code={code}&job_category_id={id}&recruit_type={type}
```

Example:
```
https://lifeattiktok.com/search?keyword=software%20engineer
```

---

## Rate Limiting & Bot Detection

### Observed Behavior

1. **302 Redirects**: API calls receive 302 Found redirects
2. **Timeouts**: Requests may timeout (>15 seconds)
3. **User Agent Checks**: Requires realistic browser user agents
4. **Cookie Requirements**: May need session cookies
5. **CSRF Tokens**: Likely required for POST requests

### Mitigation Strategies

1. **Realistic Headers**
   ```python
   headers = {
       "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
       "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
       "Accept-Language": "en-US,en;q=0.9",
       "Referer": "https://careers.tiktok.com/",
       "Origin": "https://careers.tiktok.com"
   }
   ```

2. **Session Cookies**
   - Use requests.Session() to maintain cookies
   - May need to visit landing page first to get session

3. **Rate Limiting**
   - Add delays between requests (5-10 seconds)
   - Use exponential backoff on failures
   - Rotate proxies for production

4. **JavaScript Rendering**
   - Use Selenium/Playwright for full page rendering
   - Wait for dynamic content to load

---

## Selenium/Playwright Approach

### Why Needed

- Job listings are loaded via JavaScript after initial page load
- Static HTML parsing misses dynamically rendered content
- API endpoints are protected and require browser context

### Implementation

```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("user-agent=Mozilla/5.0...")

driver = webdriver.Chrome(options=options)
driver.get("https://lifeattiktok.com/search?keyword=software+engineer")

# Wait for content to load
wait = WebDriverWait(driver, 10)
wait.until(lambda d: d.find_element("tag_name", "body"))

# Additional wait for dynamic content
import time
time.sleep(3)

# Parse rendered HTML
html = driver.page_source
# Extract jobs from html...

driver.quit()
```

---

## Alternative Data Sources

Since direct API access is not available, consider these alternatives:

### 1. Job Aggregators

**SimplifyJobs** (GitHub)
- Repo: https://github.com/SimplifyJobs/Summer2025-Internships
- Already scrapes TikTok/ByteDance postings
- JSON/Markdown format available

**RippleMatch**
- API available via fetchers/ripplematch.py
- May include TikTok positions

**NewGrad Repos**
- https://github.com/ReaVNaiL/New-Grad-2025
- Community-maintained lists

### 2. LinkedIn Jobs

TikTok posts jobs on LinkedIn which has a more accessible API (though still unofficial).

### 3. Third-Party ATS

Check if TikTok uses:
- Greenhouse
- Lever
- Workday
- iCIMS

**Finding**: TikTok/ByteDance do not use these common platforms.

### 4. RSS/Atom Feeds

**Finding**: No RSS/Atom feeds available.

---

## Known Job Examples

### TikTok New Grad 2026

**Position**: Frontend Software Engineer Graduate - 2026 Start (BS/MS)
- **Job ID**: 7531986763343300871
- **URL**: https://lifeattiktok.com/search/7531986763343300871
- **Team**: Technology - Global Live Platform
- **Type**: Full-time
- **Program**: Graduate Program

### How to Create Job Objects for Known IDs

```python
from models import Job

def create_tiktok_job(job_id: str, title: str, location: str) -> Job:
    url = f"https://lifeattiktok.com/search/{job_id}"
    raw_id = f"tiktok:{job_id}"
    uid = Job.generate_uid("tiktok", raw_id=raw_id)

    return Job(
        uid=uid,
        source_group="tiktok",
        source_name="TikTok",
        title=title,
        company="TikTok",
        location=location,
        url=url,
        raw_id=raw_id,
        snippet=""
    )
```

---

## Future Enhancement Opportunities

### 1. Job Detail Fetching

Fetch full details for each job ID:

```python
def fetch_job_details(job_id: str) -> dict:
    url = f"https://lifeattiktok.com/search/{job_id}"
    # Use Selenium to render page
    # Parse title, location, description, etc.
    return job_data
```

### 2. API Authentication Reverse Engineering

- Capture browser network traffic
- Identify auth tokens/cookies
- Replicate authentication flow
- **Warning**: May violate ToS

### 3. Webhook Monitoring

- Monitor for new job postings
- Send notifications on new listings
- Track job status changes

### 4. Proxy Rotation

```python
proxies = [
    "http://proxy1.example.com:8000",
    "http://proxy2.example.com:8000",
]

import random
proxy = random.choice(proxies)
session.proxies = {"http": proxy, "https": proxy}
```

---

## Comparison with Other Fetchers

| Company | API Type | Public Access | Rate Limits | Notes |
|---------|----------|---------------|-------------|-------|
| Google | XML Feed | Yes | Unknown | Simple and reliable |
| Lever | REST API | Yes | Generous | Used by many companies |
| Greenhouse | REST API | Yes | Generous | Used by many companies |
| TikTok | Protected | **No** | Aggressive | Requires scraping |
| ByteDance | Protected | **No** | Aggressive | Requires scraping |

---

## Recommendations

### For Development

1. **Use Selenium**: Required for reliable results
2. **Add Rate Limiting**: 5-10 second delays between requests
3. **Implement Retry Logic**: Handle timeouts and 302 redirects
4. **Monitor Logs**: Watch for bot detection patterns

### For Production

1. **Use Job Aggregators**: SimplifyJobs, RippleMatch, etc.
2. **Manual Curation**: For specific roles, manually add job IDs
3. **Hybrid Approach**: Combine automated scraping with manual updates
4. **Alert on Failures**: Track success rate and alert on degradation

### For Maintenance

1. **Regular Testing**: Page structure may change without notice
2. **Update Selectors**: Keep CSS/XPath selectors up to date
3. **Monitor Rate Limits**: Adjust delays as needed
4. **Check for API Changes**: Periodically test for new public APIs

---

## Legal & Ethical Considerations

### Terms of Service

Review TikTok/ByteDance Terms of Service regarding:
- Automated access / scraping
- Data collection restrictions
- Rate limiting policies

### Best Practices

1. **Respect robots.txt**: Check for scraping restrictions
2. **Rate Limiting**: Don't overwhelm servers
3. **Attribution**: Credit TikTok/ByteDance as source
4. **Privacy**: Don't collect PII from job postings
5. **Commercial Use**: Understand restrictions on commercial usage

---

## Resources

### Official Sites
- TikTok Careers: https://lifeattiktok.com
- ByteDance Careers: https://joinbytedance.com
- TikTok Developer Portal: https://developers.tiktok.com (not for jobs)

### Tools & Libraries
- Selenium: https://selenium-python.readthedocs.io/
- Playwright: https://playwright.dev/python/
- BeautifulSoup: https://www.crummy.com/software/BeautifulSoup/
- Requests: https://requests.readthedocs.io/

### Job Aggregators
- SimplifyJobs: https://github.com/SimplifyJobs/Summer2025-Internships
- Pitt CSC: https://github.com/pittcsc/Summer2025-Internships
- NewGrad 2025: https://github.com/ReaVNaiL/New-Grad-2025

---

## Changelog

- **2026-02-05**: Initial investigation and documentation
  - Tested 7+ API endpoints, all protected
  - Confirmed no Lever/Greenhouse integration
  - Documented Next.js data structure
  - Created fetcher implementation with Selenium support

---

## Questions & Support

For questions or issues with the TikTok/ByteDance fetcher:

1. Check logs for specific error messages
2. Review TIKTOK_FETCHER_README.md for usage instructions
3. Run test_tiktok_fetcher.py for diagnostics
4. Open an issue with relevant logs and configuration

**Common Issues**:
- 302 redirects → Bot detection, use Selenium
- Timeouts → Increase timeout, use Selenium
- 0 jobs found → Page is JavaScript-rendered, use Selenium
- Selenium errors → Check ChromeDriver installation
