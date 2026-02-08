# Workday Selenium Scraper

## Overview

Some major companies have blocked API access to their Workday job boards, returning 401/422 errors. This Selenium-based scraper navigates the web UI directly to fetch job listings.

## Affected Companies

The following 8 companies now use the Selenium scraper instead of the API:

1. **Visa** - https://visa.wd5.myworkdayjobs.com/Visa_Careers
2. **Verizon** - https://verizon.wd5.myworkdayjobs.com/verizon
3. **Fidelity** - https://fidelity.wd5.myworkdayjobs.com/Fidelity_Careers
4. **IBM** - https://ibm.wd5.myworkdayjobs.com/IBM_Careers
5. **Honeywell** - https://honeywell.wd5.myworkdayjobs.com/Honeywell_Careers
6. **Lockheed Martin** - https://lockheedmartin.wd5.myworkdayjobs.com/LMCareers
7. **Northrop Grumman** - https://northropgrumman.wd5.myworkdayjobs.com/NG_External
8. **John Deere** - https://johndeere.wd5.myworkdayjobs.com/JohnDeere

## Implementation

### Files Created/Modified

1. **fetchers/workday_selenium.py** - New Selenium-based scraper
   - Similar architecture to the Microsoft scraper
   - Handles pagination with "Load More" buttons
   - Extracts title, location, URL, posting date
   - Parses relative dates (e.g., "Posted 2 days ago")

2. **main.py** - Added `workday_selenium` to FETCHER_REGISTRY
   - Imported `WorkdaySeleniumFetcher`
   - Registered as `"workday_selenium"`

3. **config.json** - Migrated 8 companies to new section
   - Created `workday_selenium` section
   - Removed duplicates from `workday` section
   - Converted API URLs to web URLs (removed `/wday/cxs/` path)

## Configuration

Each company in the `workday_selenium` section has:

```json
{
  "name": "Company Name",
  "company": "Company Name",
  "base_url": "https://company.wd5.myworkdayjobs.com/JobBoard",
  "max_pages": 10,
  "headless": true
}
```

### Configuration Options

- `name`: Display name for the fetcher
- `company`: Company name for job listings
- `base_url`: Web URL to the Workday job board (NOT the API URL)
- `max_pages`: Maximum number of pages to scrape (default: 10)
- `headless`: Run Chrome in headless mode (default: true)

## Testing

A test script is provided to verify the scraper works:

```bash
python3 test_workday_selenium.py
```

This will:
- Test the Visa career page
- Scrape 2 pages (faster than full scrape)
- Display sample job listings
- Show first 5 jobs with full details

## Requirements

The scraper uses the same Selenium setup as the Microsoft fetcher:

- selenium
- webdriver-manager
- Chrome/Chromium browser

For VM deployment, ensure:
- Chromium is installed at `/usr/bin/chromium`
- ChromeDriver version 144.0.7559.109 matches the Chromium version

## How It Works

1. **Navigation**: Opens the Workday career page
2. **Cookie Consent**: Automatically accepts cookie banner if present
3. **Job Extraction**: Finds all job listings using CSS selectors:
   - `li[data-automation-id='listItem']` - Job cards
   - `a[data-automation-id='jobTitle']` - Job title and URL
   - `dd[data-automation-id='location']` - Location
   - `dd[data-automation-id='postedOn']` - Posted date
4. **Pagination**: Clicks "Load More" button to fetch additional pages
5. **Date Parsing**: Converts relative dates to absolute timestamps

## Differences from API Fetcher

| Feature | API Fetcher | Selenium Fetcher |
|---------|-------------|------------------|
| Speed | Fast (direct HTTP) | Slower (browser rendering) |
| Reliability | Fails with 401/422 | Works for blocked sites |
| Resource Usage | Low | Higher (Chrome process) |
| Job Data | Full details | UI-visible data only |
| Setup | Simple | Requires Chromium/ChromeDriver |

## Troubleshooting

### Common Issues

1. **"selenium not installed"**
   - Install: `pip install selenium webdriver-manager`

2. **ChromeDriver version mismatch**
   - Check Chromium version: `chromium --version`
   - Update driver version in fetcher if needed

3. **No jobs found**
   - Check `base_url` is correct (web URL, not API URL)
   - Verify job board is publicly accessible
   - Try non-headless mode to see browser errors

4. **Timeout errors**
   - Increase page load timeout (currently 30s)
   - Check network connectivity
   - Verify Workday site is not down

## Future Improvements

- Add support for search filters (location, job type, etc.)
- Implement job description scraping (requires clicking into detail pages)
- Add retry logic for transient failures
- Cache ChromeDriver to avoid repeated downloads
- Support custom CSS selectors per company (if HTML varies)

## Notes

- The scraper respects rate limits with 2-3 second delays between pages
- UIDs are generated from job URLs (same as API fetcher)
- Source group remains `"workday"` for consistency
- Posted dates use relative parsing (may be approximate)
