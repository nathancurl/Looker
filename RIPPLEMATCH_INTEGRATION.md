# Ripplematch Integration

This document describes the Ripplematch integration added to the job notification system.

## Overview

Ripplematch has been integrated using Selenium-based web scraping (similar to Wellfound) since they don't provide a public API or RSS feed.

## What Was Added

### 1. Fetcher Implementation
- **File**: `fetchers/ripplematch.py`
- **Type**: Selenium-based scraper
- **Target URL**: https://ripplematch.com/jobs/computer-science-majors/
- **Method**: Headless Chrome browser automation

### 2. Configuration Updates
- Added to `config.json`:
  - Routing: `"ripplematch": "DISCORD_WEBHOOK_RIPPLEMATCH"`
  - Source config: Poll interval of 3600 seconds (1 hour)
  - Max scrolls: 15 (configurable)

### 3. Environment Variables
- Added to `.env.example`: `DISCORD_WEBHOOK_RIPPLEMATCH=`
- Users need to add their webhook URL to `.env`

### 4. Main Registry
- Registered `RipplematchFetcher` in `main.py`
- Added to imports and `FETCHER_REGISTRY`

### 5. Documentation
- Updated `README.md` with Ripplematch in startup boards section
- Added webhook configuration example

### 6. Tests
- **File**: `tests/test_fetchers/test_ripplematch.py`
- 7 test cases covering:
  - Selenium import handling
  - HTML parsing
  - Title/company extraction
  - Error handling
  - Deduplication
  - Realistic job ID formats

### 7. Validation Script
- **File**: `scripts/test_ripplematch.py`
- Quick test script to validate the fetcher works
- Usage: `poetry run python scripts/test_ripplematch.py`

## How It Works

1. **Browser Launch**: Opens headless Chrome via Selenium
2. **Page Load**: Navigates to Ripplematch's computer science jobs page
3. **Scrolling**: Scrolls down up to 15 times to load more jobs
4. **Parsing**: Extracts job URLs matching pattern:
   - `https://app.ripplematch.com/v2/public/job/{job_id}`
5. **Job Creation**: Creates Job objects with:
   - UID: `ripplematch:{job_id}`
   - Title: Extracted from surrounding HTML (or fallback)
   - Company: Extracted from context (or "Unknown")
   - URL: Cleaned (query params removed)

## Configuration

Edit `config.json` to customize:

```json
{
  "ripplematch": {
    "name": "Ripplematch",
    "max_scrolls": 15,        // Number of page scrolls
    "headless": true,          // Run in headless mode
    "poll_interval_seconds": 3600  // How often to check (1 hour)
  }
}
```

## Setup

1. **Install Chrome/Chromium** (required for Selenium):
   ```bash
   # macOS
   brew install --cask google-chrome

   # Ubuntu/Debian
   sudo apt-get install chromium-browser

   # Or download from https://www.google.com/chrome/
   ```

2. **Install dependencies** (already done if using Poetry):
   ```bash
   poetry install
   ```
   Selenium and webdriver-manager are included in dependencies.

3. **Add Discord webhook**:
   ```bash
   # Add to .env
   DISCORD_WEBHOOK_RIPPLEMATCH=https://discord.com/api/webhooks/YOUR_WEBHOOK_HERE
   ```

4. **Test the fetcher**:
   ```bash
   poetry run python scripts/test_ripplematch.py
   ```

5. **Run the bot**:
   ```bash
   poetry run python main.py
   ```

## Limitations

1. **Fragile**: Web scraping is fragile and may break when Ripplematch updates their UI
2. **Slow**: Selenium is slower than API calls (~15-30 seconds per fetch)
3. **Resource intensive**: Requires Chrome/Chromium browser
4. **Title/Company extraction**: May not always be accurate due to HTML structure changes
5. **No official support**: Not using an official API, so could violate ToS

## Maintenance

This fetcher will require periodic maintenance when:
- Ripplematch updates their HTML structure
- CSS selectors change
- URL patterns change
- Anti-bot measures are enhanced

Monitor logs for errors like:
- "Ripplematch: no job links found on page"
- "Ripplematch: browser error"

## Testing

Run tests with:
```bash
# All tests
poetry run pytest tests/test_fetchers/test_ripplematch.py -v

# Specific test
poetry run pytest tests/test_fetchers/test_ripplematch.py::TestRipplematchFetcher::test_parse_jobs_from_html -v
```

All 7 tests should pass.

## Job URL Pattern

Jobs are identified by URLs like:
- `https://app.ripplematch.com/v2/public/job/9812a228`
- `https://app.ripplematch.com/v2/public/job/0e293ec3`
- `https://app.ripplematch.com/v2/public/job/e9541a54`

Job IDs are hexadecimal strings (8 characters) that serve as unique identifiers.

## Alternatives Considered

1. **RSS Feed**: Not available
2. **Public API**: Not available
3. **Contact for API access**: Could reach out to help@ripplematch.com
4. **Don't add Ripplematch**: Decision was to proceed with Selenium scraper

## Future Improvements

1. Better title/company extraction with more robust regex patterns
2. Support for different job category pages (not just CS majors)
3. Location extraction
4. Remote job detection
5. Posted date extraction if available
6. Retry logic for transient failures
7. Screenshot capture on errors for debugging
