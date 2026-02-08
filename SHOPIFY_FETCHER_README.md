# Shopify Job Fetcher

A custom fetcher for retrieving job listings from Shopify's career site.

## Overview

Shopify uses a custom React-based careers portal that loads job data dynamically via JavaScript. Unlike many other companies, Shopify does not use a third-party ATS (Applicant Tracking System) like Greenhouse, Lever, or Workday, and they do not expose a public API for job listings.

## Career Site Information

- **Main Career Site**: https://www.shopify.com/careers
- **Search Page**: https://www.shopify.com/careers/search
- **Job URL Pattern**: `/careers/{job-title}_{uuid}`
- **Example**: `https://www.shopify.com/careers/usa-engineering-internships-summer-2026-usa_b2dbdf1e-ab44-46ed-9a11-69a1a1e4b20c`

## API Structure

### No Public API

Shopify does not provide a public API for job listings. The fetcher works by:
1. Scraping the HTML from the main careers page
2. Extracting job links using regex patterns
3. Parsing job titles from URL slugs

### Job URL Pattern

Jobs follow this consistent pattern:
```
/careers/{job-slug}_{uuid}
```

Where:
- `job-slug` is a hyphen-separated lowercase title (e.g., `senior-software-engineer`)
- `uuid` is a standard UUID v4 (e.g., `b2dbdf1e-ab44-46ed-9a11-69a1a1e4b20c`)

## Rate Limits

**Rate limits are strict and not publicly documented.**

Observations:
- The search endpoint (`/careers/search`) appears to have stricter rate limiting
- The main careers page (`/careers`) is more lenient but still rate-limited
- 429 (Too Many Requests) errors occur after multiple rapid requests
- Recommended: Wait 5-10 minutes between fetches

## Fetcher Implementation

### File Location
```
fetchers/shopify.py
```

### Configuration

#### Basic Configuration
```json
{
  "name": "Shopify",
  "fetcher": "shopify",
  "company": "Shopify"
}
```

#### With Keyword Filtering
```json
{
  "name": "Shopify Early Career",
  "fetcher": "shopify",
  "company": "Shopify",
  "keywords": ["intern", "new grad", "engineer", "software", "developer"]
}
```

#### With Selenium (for better JavaScript support)
```json
{
  "name": "Shopify Selenium",
  "fetcher": "shopify",
  "company": "Shopify",
  "use_selenium": true,
  "keywords": ["engineer", "software"]
}
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `name` | string | Required | Display name for the source |
| `fetcher` | string | Required | Must be "shopify" |
| `company` | string | Required | Company name (typically "Shopify") |
| `keywords` | list[string] | [] | Filter jobs by keywords in title |
| `use_selenium` | boolean | false | Use Selenium for JavaScript rendering |

## Usage

### Basic Usage

```python
from fetchers.shopify import ShopifyFetcher

config = {
    "name": "Shopify",
    "company": "Shopify"
}

fetcher = ShopifyFetcher(config)
jobs = fetcher.safe_fetch()

for job in jobs:
    print(f"{job.title} - {job.url}")
```

### With Keyword Filtering

```python
from fetchers.shopify import ShopifyFetcher

config = {
    "name": "Shopify Engineering",
    "company": "Shopify",
    "keywords": ["engineer", "software", "developer", "intern"]
}

fetcher = ShopifyFetcher(config)
jobs = fetcher.safe_fetch()

print(f"Found {len(jobs)} engineering positions")
```

### Testing

Run the test script:
```bash
python test_shopify_fetcher.py
```

This will run three test scenarios:
1. Basic fetch without filters
2. Fetch with keyword filters
3. Fetch with Selenium (optional)

## Early Career Programs

Shopify offers several structured programs for early career candidates:

1. **Dev Degree Program**
   - 3-4 year program
   - Earn CS degree while working
   - Targets: High school graduates

2. **Engineering Internships**
   - 4-month paid internships
   - Open to students, recent graduates, and early career
   - Multiple locations (USA, Canada, etc.)

3. **Apprentice Product Manager (APM) Program**
   - 12-month program
   - Product management focus

4. **Design Apprentice Program**
   - 12-month program
   - Built for new graduates and career switchers
   - Includes mentorship and rotations

### Finding Early Career Positions

Use these keywords to filter for new grad/early career positions:
- "intern" or "internship"
- "new grad" or "new graduate"
- "early career"
- "apprentice"
- "dev degree"

Example configuration:
```json
{
  "name": "Shopify New Grad",
  "fetcher": "shopify",
  "company": "Shopify",
  "keywords": ["intern", "new grad", "early career", "apprentice", "dev degree"]
}
```

## Limitations

### 1. JavaScript Rendering
- Jobs are loaded dynamically via React
- The basic fetcher only sees server-side rendered content
- Some jobs may not appear without JavaScript execution
- **Solution**: Use `use_selenium: true` for better coverage

### 2. Rate Limiting
- Aggressive rate limiting on the search endpoint
- Multiple rapid requests will result in 429 errors
- **Solution**: Space out requests, use longer polling intervals

### 3. No Structured Data
- No JSON API or structured data
- Job details must be parsed from HTML
- No official API documentation
- **Risk**: Site structure changes could break the fetcher

### 4. Limited Metadata
- Cannot extract job descriptions without visiting individual pages
- Location is set to "Remote" (Shopify is "Digital by Design")
- No posted date information available
- No department/category information in the job list

### 5. Password-Protected Postings
- Some positions (e.g., 2026 internships) are password-protected
- These cannot be scraped or accessed programmatically
- They appear in search results but show "PRIVATE JOB POSTING"

## Selenium Setup (Optional)

For better JavaScript support, you can use Selenium:

### Installation

```bash
# Install Selenium
pip install selenium

# Install ChromeDriver (macOS with Homebrew)
brew install chromedriver

# Or download from: https://chromedriver.chromium.org/
```

### Configuration

Set `use_selenium: true` in your configuration:

```json
{
  "name": "Shopify Selenium",
  "fetcher": "shopify",
  "company": "Shopify",
  "use_selenium": true
}
```

### Benefits of Selenium

- Executes JavaScript, revealing dynamically loaded jobs
- Better coverage of job listings
- Can interact with search filters

### Drawbacks of Selenium

- Slower than requests-based scraping
- Requires additional dependencies (chromedriver)
- Higher resource usage
- Still subject to rate limiting

## Best Practices

1. **Polling Frequency**
   - Recommend: Once per day or less
   - Minimum: Wait 10 minutes between requests
   - Monitor for 429 errors and back off if they occur

2. **Keyword Filtering**
   - Use specific keywords to reduce noise
   - Combine multiple relevant terms
   - Filter client-side to avoid search endpoint rate limits

3. **Error Handling**
   - The fetcher gracefully handles rate limits
   - Returns empty list on failure
   - Logs warnings for debugging

4. **User Agent**
   - Uses Mozilla User-Agent to appear as a browser
   - Identifies as job-notification-discord in logs

## Troubleshooting

### No Jobs Found

**Possible causes:**
- Rate limited (check logs for 429 errors)
- Site structure changed
- Keywords too restrictive
- Jobs are JavaScript-loaded only

**Solutions:**
1. Wait 10+ minutes and retry
2. Try without keywords first
3. Enable Selenium: `use_selenium: true`
4. Check if the site is accessible in a browser

### Rate Limited (429 Error)

**Message:** `Shopify: rate limited. Wait a few minutes before retrying.`

**Solutions:**
1. Wait 10-15 minutes before next request
2. Reduce polling frequency in config
3. Use main careers page instead of search
4. Consider rotating IPs (advanced)

### Selenium Not Working

**Error:** `ModuleNotFoundError: No module named 'selenium'`

**Solution:**
```bash
pip install selenium
```

**Error:** `chromedriver not found`

**Solution:**
```bash
# macOS
brew install chromedriver

# Linux
sudo apt-get install chromium-chromedriver

# Or download manually from:
# https://chromedriver.chromium.org/
```

## Future Improvements

Potential enhancements for this fetcher:

1. **Individual Page Scraping**
   - Visit each job page to extract full details
   - Get description, requirements, and metadata
   - Extract actual location information

2. **Smart Rate Limiting**
   - Implement exponential backoff
   - Track rate limit windows
   - Auto-adjust polling frequency

3. **Department Filtering**
   - Extract department/discipline information
   - Filter by Engineering, Design, Product, etc.

4. **Caching**
   - Cache job listings to reduce requests
   - Only fetch updates since last check
   - Detect new/removed positions

5. **Playwright Support**
   - Modern alternative to Selenium
   - Better performance and reliability
   - Native async support

## Source Code

The fetcher implementation: `/Users/ncurl/side-projects/job-notification-discord/fetchers/shopify.py`

Test script: `/Users/ncurl/side-projects/job-notification-discord/test_shopify_fetcher.py`

## Related Documentation

- Main README: [README.md](README.md)
- Fetcher Base Class: [fetchers/base.py](fetchers/base.py)
- Job Model: [models.py](models.py)

## Support and Contributions

For issues or improvements:
1. Check existing fetchers for similar patterns
2. Test thoroughly with different configurations
3. Document any site structure changes
4. Consider rate limiting in all changes

## Legal and Ethical Considerations

- Respect Shopify's rate limits
- Only use for legitimate job searching purposes
- Do not abuse or overload their servers
- Follow robots.txt guidelines
- Be transparent about automated access

---

**Last Updated:** 2026-02-05
