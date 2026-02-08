# Goldman Sachs Fetcher Documentation

## Overview

The Goldman Sachs fetcher retrieves job postings from their careers platform at **higher.gs.com**. This is a custom careers platform built with modern web technologies.

## Technical Architecture

### Platform: Higher

Goldman Sachs uses a proprietary platform called "Higher" for their careers site. Key characteristics:

- **Framework**: Next.js (React-based)
- **Data Layer**: Apollo GraphQL
- **CMS**: Contentful (for content management)
- **Rendering**: Server-side + Client-side hybrid
- **Build ID**: `dab3d37481e81fb56a6c41211f838bc273f2fe41` (as of Feb 2026)

### API Structure

The site uses a **GraphQL API** for job data that loads client-side via Apollo. Key findings from investigation:

1. **Initial Page Load**: Returns empty `initialApolloState: {}`
2. **Data Loading**: Client-side JavaScript makes GraphQL requests after page load
3. **Endpoint**: Likely `https://higher.gs.com/api/graphql` or similar (needs confirmation)
4. **Authentication**: May require session cookies, CSRF tokens, or API keys

### URL Structure

- **Main Search**: `https://higher.gs.com/results`
- **With Filters**: `https://higher.gs.com/results?division=Engineering&careers_level=New%20Analyst`
- **Job Detail**: `https://higher.gs.com/roles/{job_id}`
- **Next.js Data**: `https://higher.gs.com/_next/data/{buildId}/results.json`

### Filter Parameters

Based on the site investigation, common filter parameters include:

- `division`: Department/division (e.g., "Engineering", "Investment Banking")
- `careers_level`: Experience level (e.g., "New Analyst", "Summer Analyst", "Analyst")
- `regions`: Geographic region (e.g., "Americas", "EMEA", "APAC")
- `locations`: Specific cities/countries
- `type`: Job type (e.g., "Full-time", "Internship")

## Current Implementation Status

### What Works

- ✅ Fetcher class structure following BaseFetcher pattern
- ✅ Multiple fallback strategies (GraphQL, page scraping, embedded data)
- ✅ Job parsing with flexible field extraction
- ✅ Location formatting and remote detection
- ✅ Proper error handling and logging

### What Needs Completion

- ⚠️ **GraphQL Endpoint Discovery** - Requires browser DevTools inspection
- ⚠️ **GraphQL Query Structure** - Needs actual query from network requests
- ⚠️ **Authentication Details** - May need tokens, cookies, or headers
- ⚠️ **Rate Limits** - Unknown, needs testing and monitoring

## Setup Instructions

### Step 1: Discover the GraphQL API

1. **Open Browser DevTools**:
   ```bash
   # Open Chrome with DevTools
   # Navigate to: https://higher.gs.com/results
   # Open DevTools: F12 or Cmd+Option+I
   ```

2. **Monitor Network Traffic**:
   - Go to the **Network** tab
   - Filter for **Fetch/XHR** or search for "graphql"
   - Apply filters on the page (Engineering + New Analyst)
   - Look for POST requests

3. **Examine the Request**:
   - Click on the GraphQL request
   - **Headers** tab: Copy any required headers (Authorization, x-api-key, etc.)
   - **Payload** tab: Copy the GraphQL query and variables
   - **Response** tab: Study the response structure

4. **Document Your Findings**:
   ```json
   {
     "endpoint": "https://higher.gs.com/api/...",
     "method": "POST",
     "headers": {
       "Content-Type": "application/json",
       "X-API-Key": "...",
       "Cookie": "..."
     },
     "query": "query SearchJobs($filters: ...) { ... }",
     "variables": {
       "filters": { ... }
     }
   }
   ```

### Step 2: Update the Fetcher Configuration

Edit your `config.json` or configuration file:

```json
{
  "sources": [
    {
      "name": "Goldman Sachs Engineering",
      "fetcher_class": "goldmansachs",
      "company": "Goldman Sachs",
      "enabled": true,
      "graphql_endpoint": "https://higher.gs.com/api/graphql",
      "graphql_query": "query SearchJobs($filters: JobFilters) { searchJobs(filters: $filters) { results { id title location description url } } }",
      "filters": {
        "division": ["Engineering"],
        "careers_level": ["New Analyst", "Summer Analyst"],
        "regions": ["Americas"]
      }
    }
  ]
}
```

### Step 3: Update Fetcher Code (if needed)

If authentication is required, update `/fetchers/goldmansachs.py`:

```python
def _fetch_via_graphql(self, session: requests.Session) -> list[Job]:
    # Add required headers
    headers = {
        "X-API-Key": "YOUR_API_KEY",  # If required
        "X-CSRF-Token": "...",  # If required
    }
    session.headers.update(headers)

    # Rest of the method...
```

### Step 4: Test the Fetcher

```bash
# Run the test script
python3 test_goldmansachs.py

# Or test directly in Python
python3 -c "
from fetchers.goldmansachs import GoldmanSachsFetcher
config = {'name': 'GS', 'company': 'Goldman Sachs'}
fetcher = GoldmanSachsFetcher(config)
jobs = fetcher.safe_fetch()
print(f'Fetched {len(jobs)} jobs')
"
```

## Alternative Approach: Browser Automation

If the GraphQL API is too complex or protected, consider browser automation:

### Option 1: Playwright (Recommended)

```python
from playwright.sync_api import sync_playwright

def fetch_via_playwright(filters: dict) -> list[dict]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Navigate to results page
        page.goto("https://higher.gs.com/results")

        # Apply filters
        page.click('button[aria-label="Filters"]')
        # ... select filters ...

        # Wait for jobs to load
        page.wait_for_selector('[data-testid="job-card"]')

        # Extract job data
        jobs = page.eval_on_selector_all(
            '[data-testid="job-card"]',
            "els => els.map(el => ({ title: el.querySelector('h3')?.textContent, ... }))"
        )

        browser.close()
        return jobs
```

### Option 2: Selenium

```python
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

def fetch_via_selenium(filters: dict) -> list[dict]:
    driver = webdriver.Chrome()
    driver.get("https://higher.gs.com/results")

    # Wait for jobs to load
    WebDriverWait(driver, 10).until(
        lambda d: d.find_elements(By.CSS_SELECTOR, '[data-testid="job-card"]')
    )

    # Extract jobs
    job_elements = driver.find_elements(By.CSS_SELECTOR, '[data-testid="job-card"]')
    jobs = []
    for el in job_elements:
        jobs.append({
            'title': el.find_element(By.TAG_NAME, 'h3').text,
            # ... extract other fields ...
        })

    driver.quit()
    return jobs
```

## API Response Structure

Based on typical GraphQL career APIs, expect a structure like:

```json
{
  "data": {
    "searchJobs": {
      "results": [
        {
          "id": "123456",
          "title": "2026 | Americas | New York | Engineering | Software Engineer",
          "description": "Job description...",
          "location": {
            "city": "New York",
            "state": "NY",
            "country": "United States"
          },
          "division": "Engineering",
          "level": "New Analyst",
          "url": "https://higher.gs.com/roles/123456",
          "posted_date": "2026-01-15",
          "type": "Full-time"
        }
      ],
      "totalCount": 50,
      "pageInfo": {
        "hasNextPage": true,
        "endCursor": "cursor123"
      }
    }
  }
}
```

## Rate Limits

**Status**: Unknown - needs testing

**Recommendations**:
- Start with conservative delays (2-3 seconds between requests)
- Monitor for 429 (Too Many Requests) errors
- Implement exponential backoff on failures
- Consider caching results for 1-6 hours
- Respect robots.txt and terms of service

**Current Implementation**:
- Uses `resilient_post` with retry logic (3 attempts)
- 15-second timeout on requests
- No artificial delays yet (add if needed)

## Filtering for New Grad Roles

The fetcher is configured to focus on early career software engineering positions:

### Recommended Filters

```python
{
    "division": ["Engineering"],
    "careers_level": [
        "New Analyst",      # Entry-level full-time
        "Summer Analyst",   # Summer internships
        "Analyst"           # Early career roles
    ],
    "regions": ["Americas"],  # Or ["Americas", "EMEA"] for broader search
}
```

### Keywords in Titles

Common patterns in Goldman Sachs engineering titles:
- `2026 | Americas | {City} | Engineering | {Role}`
- `Summer Analyst - Engineering`
- `New Analyst - Software Engineering`
- `Technology Analyst - Engineering`

## Troubleshooting

### Issue: No Jobs Returned

**Solutions**:
1. Verify GraphQL endpoint is correct
2. Check if authentication is required (cookies, tokens)
3. Validate GraphQL query syntax
4. Inspect response for error messages
5. Enable debug logging: `logging.getLogger('fetchers.goldmansachs').setLevel(logging.DEBUG)`

### Issue: 403 Forbidden

**Possible Causes**:
- Missing authentication headers
- Invalid or expired session cookies
- User-Agent blocking
- Rate limiting

**Solutions**:
- Add required authentication headers
- Use realistic User-Agent string (already configured)
- Implement request delays
- Consider browser automation approach

### Issue: Empty Apollo State

**Explanation**: The site loads data client-side, so server-side rendered pages have empty state.

**Solutions**:
- Use the GraphQL endpoint directly (preferred)
- Use browser automation to render JavaScript
- Look for alternative data endpoints

## Maintenance Notes

### Monitoring

Monitor these indicators for API changes:

1. **Build ID changes**: Check `https://higher.gs.com/_next/data/{buildId}/results.json`
2. **GraphQL schema changes**: Watch for new fields or deprecated fields
3. **Filter parameter changes**: New or renamed filter options
4. **Rate limit adjustments**: Track 429 errors

### Updating

When the site updates:

1. Check if GraphQL endpoint changed
2. Verify GraphQL query still works
3. Test filter parameters
4. Update field mappings if response structure changed
5. Re-run test suite: `python3 test_goldmansachs.py`

## References

- [Higher Platform](https://higher.gs.com)
- [Goldman Sachs Careers](https://higher.gs.com/results)
- [Contentful CMS](https://www.contentful.com) (used by Higher)
- [Apollo GraphQL](https://www.apollographql.com)
- [Next.js Documentation](https://nextjs.org/docs)

## Contact

For issues or questions about this fetcher:
1. Check logs for error messages
2. Review this documentation
3. Test with `python3 test_goldmansachs.py`
4. Refer to `/fetchers/goldmansachs.py` source code

## Related Sources

Based on web search findings:

- [Higher.gs.com Opportunities](https://higher.gs.com/results)
- [Goldman Sachs Developer Portal](https://developer.gs.com/docs/)
- [API Tracker - Goldman Sachs API](https://apitracker.io/a/goldmansachs)

Note: The developer.gs.com portal is for Goldman Sachs' financial APIs (Legend, Marcus, etc.), not for careers data. The Higher platform uses a separate, internal API.
