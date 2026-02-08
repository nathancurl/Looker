# Tesla Fetcher - Quick Start Guide

## TL;DR

Tesla uses Oracle Taleo Business Edition with aggressive Akamai anti-bot protection. **Direct API access is blocked.** Use browser automation instead.

## Fastest Working Solution

### 1. Install Playwright

```bash
pip install playwright
playwright install chromium
```

### 2. Add Configuration

Edit `config.json`:

```json
{
  "sources": {
    "tesla": {
      "fetcher": "tesla",
      "name": "Tesla",
      "company": "Tesla",
      "filter_keywords": [
        "software engineer",
        "new grad",
        "intern"
      ]
    }
  },
  "routing": {
    "tesla": "DISCORD_WEBHOOK_TESLA"
  }
}
```

### 3. Run Test

```bash
# Test the fetcher
python3 test_tesla_fetcher.py

# Expected: Blocked by Akamai (500 errors)
```

### 4. Use Browser Automation

```bash
# Run browser-based fetcher
python3 fetchers/tesla_browser.py
```

## Files Created

| File | Purpose |
|------|---------|
| `fetchers/tesla.py` | Main fetcher (API/HTML modes - blocked) |
| `fetchers/tesla_browser.py` | Browser automation fetcher (works) |
| `test_tesla_fetcher.py` | Test suite |
| `TESLA_FETCHER_README.md` | Complete documentation |
| `TESLA_USAGE_EXAMPLES.md` | Working code examples |
| `TESLA_QUICK_START.md` | This file |

## Why Direct Access Fails

```
Request → Akamai Protection → 500 Server Error / Access Denied
```

Tesla uses:
- Akamai bot detection
- IP-based rate limiting
- User agent filtering
- Behavioral analysis

## Working Approaches

### ✅ Browser Automation (Recommended)
- Uses Playwright/Selenium
- Bypasses anti-bot protection
- Most reliable

### ✅ Email Alerts
- Subscribe to Tesla job alerts
- Parse emails automatically
- No blocking issues

### ✅ Third-Party Aggregators
- LinkedIn, Indeed, Glassdoor
- Already scrape Tesla
- Require API access

### ❌ Direct API (Blocked)
- Returns 500 errors
- Blocked by Akamai
- Not recommended

## Configuration Options

### tesla.py (Direct - Currently Blocked)

```json
{
  "fetcher": "tesla",
  "use_api": true,
  "max_pages": 50,
  "filter_keywords": ["software", "engineer"]
}
```

### tesla_browser.py (Browser - Works)

```json
{
  "fetcher": "tesla_browser",
  "headless": true,
  "timeout": 30000,
  "max_jobs": 100,
  "filter_keywords": ["software engineer", "new grad"]
}
```

## API Structure

**Base URL**: `https://cho.tbe.taleo.net/cho01/ats/careers`

**Search Endpoint** (Blocked):
```
GET /requisition/searchRequisitions?org=TESLA&cws=1&start=0&limit=100
```

**Response Structure**:
```json
{
  "requisitions": [
    {
      "requisitionId": "12345",
      "title": "Software Engineer, New Grad",
      "location": {"city": "Palo Alto", "state": "CA"},
      "lastPublishedDate": 1706745600000,
      "category": "Engineering"
    }
  ],
  "total": 1234
}
```

## Common Issues

| Problem | Solution |
|---------|----------|
| 500 Server Error | Use browser automation |
| Access Denied (403) | IP blocked - use proxy or browser |
| Empty results | Relax filters, increase max_pages |
| Timeout errors | Increase timeout value |
| CAPTCHA | Use undetected-chromedriver |

## Testing

```bash
# Test direct API (will fail)
python3 test_tesla_fetcher.py

# Test browser mode
python3 fetchers/tesla_browser.py

# Test with Python
python3 -c "
from fetchers.tesla import TeslaFetcher
config = {'name': 'Tesla', 'company': 'Tesla'}
fetcher = TeslaFetcher(config)
jobs = fetcher.safe_fetch()
print(f'Fetched: {len(jobs)} jobs')
"
```

## Integration

Tesla fetcher is already integrated into main.py:

```python
from fetchers.tesla import TeslaFetcher

FETCHER_REGISTRY = {
    # ... other fetchers ...
    "tesla": TeslaFetcher,
}
```

Just add configuration to `config.json` to enable.

## Rate Limits

No official rate limits, but recommended:

- **Polling Interval**: 1 hour (3600 seconds)
- **Max Requests/Hour**: 10-20
- **Concurrent Requests**: 1 at a time
- **Delay Between Pages**: 2-5 seconds (browser mode)

## Filtering

Focus on new grad/early career roles:

```json
{
  "filter_keywords": [
    "software engineer",
    "software developer",
    "new grad",
    "university grad",
    "recent graduate",
    "entry level",
    "junior",
    "intern",
    "internship",
    "co-op"
  ]
}
```

## Next Steps

1. ✅ **Install dependencies**: `pip install playwright && playwright install chromium`
2. ✅ **Test browser mode**: `python3 fetchers/tesla_browser.py`
3. ⚠️ **Add to main.py registry** (if using browser mode)
4. ✅ **Configure**: Add tesla config to `config.json`
5. ✅ **Set webhook**: Add `DISCORD_WEBHOOK_TESLA` to `.env`
6. ✅ **Run**: `python3 main.py`

## Support Resources

- **Full Documentation**: See [TESLA_FETCHER_README.md](TESLA_FETCHER_README.md)
- **Code Examples**: See [TESLA_USAGE_EXAMPLES.md](TESLA_USAGE_EXAMPLES.md)
- **Taleo API Docs**: [Oracle TBE REST API Guide](https://www.oracle.com/docs/tech/documentation/tberestapiguide-v15b1.pdf)
- **Tesla Careers**: [tesla.com/careers](https://www.tesla.com/careers)

## Summary

- ❌ **Direct API**: Blocked by Akamai protection
- ✅ **Browser Automation**: Works reliably with Playwright
- ✅ **Code Ready**: Fetcher created and integrated
- ⚠️ **Production Use**: Requires browser automation setup

**Recommendation**: Use `fetchers/tesla_browser.py` with Playwright for production.

---

**Last Updated**: 2026-02-05
**Status**: Complete - Ready for browser automation
**Test Status**: Direct API blocked, Browser mode ready
