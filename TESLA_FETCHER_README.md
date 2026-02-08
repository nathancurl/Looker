# Tesla Fetcher Implementation

## Overview

The Tesla fetcher (`fetchers/tesla.py`) has been updated to use Selenium with anti-detection measures to scrape Tesla's career page. The implementation follows the same pattern as `wellfound.py` and `ripplematch.py`.

## Current Status

**⚠️ IMPORTANT:** Tesla uses aggressive Akamai bot protection that currently blocks automated requests, even with Selenium and anti-detection measures.

The fetcher is **fully implemented** with:
- ✅ Selenium integration with headless Chrome
- ✅ Anti-detection measures (stealth JavaScript, realistic user agent, etc.)
- ✅ Job extraction from DOM and HTML parsing
- ✅ Proper UID generation using `Job.generate_uid()`
- ✅ Filtering for software engineering / new grad positions
- ✅ Error handling and logging
- ✅ Integration with BaseFetcher pattern

However:
- ❌ Akamai blocks automated requests (returns "Access Denied" page)
- ❌ Cannot currently fetch live jobs without manual intervention

## Testing

### Test Parsing Logic (Works)
```bash
poetry run python test_tesla_parsing.py
```

This demonstrates that the HTML parsing and job extraction logic works correctly with mock data.

### Test Live Fetching (Currently Blocked)
```bash
poetry run python test_tesla.py
```

This attempts to fetch live jobs but will be blocked by Akamai.

## Potential Solutions

### 1. Manual CAPTCHA Solving
Set `headless=False` in config to see the browser and manually solve any CAPTCHAs:

```python
config = {
    "name": "tesla",
    "headless": False,  # Show browser window
    "max_scrolls": 10
}
```

### 2. Residential Proxies
Use a residential proxy service (e.g., BrightData, Oxylabs) that can bypass Akamai.

### 3. Scraping Services
Use a managed scraping service that handles bot protection:
- ScrapingBee
- ScraperAPI
- BrightData's Scraping Browser

### 4. Official API Access
Contact Tesla/Oracle to request official API access for job listings.

## Configuration

Add to your sources configuration:

```python
{
    "name": "tesla",
    "fetcher_class": "TeslaFetcher",
    "headless": True,
    "max_scrolls": 10,
    "filter_keywords": [
        "software",
        "engineer",
        "developer",
        "programming",
        "new grad",
        "university",
        "recent graduate",
        "entry level",
        "early career"
    ],
    "url": "https://www.tesla.com/careers/search/"
}
```

## Implementation Details

### Anti-Detection Measures
1. **Realistic User Agent**: Uses macOS Chrome user agent
2. **Stealth JavaScript**: Masks `navigator.webdriver` and other automation indicators
3. **Session Establishment**: Visits homepage before careers page
4. **Random Delays**: Uses random sleep times to mimic human behavior
5. **Experimental Options**: Disables automation flags

### Job Extraction
1. **DOM Parsing**: Extracts jobs from Selenium's DOM using multiple selectors
2. **HTML Fallback**: Parses HTML with regex if DOM extraction fails
3. **Multiple Patterns**: Tries various URL patterns (Taleo requisitions, direct job links)
4. **Title Extraction**: Intelligently extracts job titles from link text and context

The fetcher is ready to use once bot protection is bypassed!
