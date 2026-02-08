# Tesla Fetcher Usage Examples

Complete guide with working examples for integrating Tesla job fetcher.

## Quick Start

### 1. Basic Configuration

Add to `config.json`:

```json
{
  "sources": {
    "tesla": {
      "fetcher": "tesla",
      "name": "Tesla",
      "company": "Tesla",
      "use_api": true,
      "max_pages": 50,
      "filter_keywords": [
        "software engineer",
        "new grad",
        "university",
        "entry level"
      ]
    }
  },
  "routing": {
    "tesla": "DISCORD_WEBHOOK_TESLA"
  }
}
```

Add to `.env`:

```bash
DISCORD_WEBHOOK_TESLA=https://discord.com/api/webhooks/YOUR_WEBHOOK_URL
```

### 2. Run the Fetcher

```bash
# Standard mode (will likely be blocked by Akamai)
python3 main.py
```

**Expected Result**: No jobs fetched due to anti-bot protection.

## Working Solutions

### Option 1: Browser Automation (Recommended)

The browser automation fetcher bypasses Akamai by using a real browser.

#### Installation

```bash
# Install Playwright
pip install playwright

# Install browser binaries
playwright install chromium
```

#### Configuration

Update `config.json` to use browser fetcher:

```json
{
  "sources": {
    "tesla_browser": {
      "fetcher": "tesla_browser",
      "name": "Tesla (Browser)",
      "company": "Tesla",
      "headless": true,
      "timeout": 30000,
      "max_jobs": 100,
      "filter_keywords": [
        "software engineer",
        "software developer",
        "new grad",
        "university grad",
        "intern"
      ]
    }
  }
}
```

#### Run

```bash
# Test directly
python3 fetchers/tesla_browser.py

# Or integrate with main.py (requires updating FETCHER_REGISTRY)
python3 main.py
```

#### Debugging Mode

To see what the browser sees:

```python
config = {
    "name": "Tesla",
    "company": "Tesla",
    "headless": False,  # Show browser window
    "timeout": 60000,   # Longer timeout
    "filter_keywords": []
}

from fetchers.tesla_browser import TeslaBrowserFetcher
fetcher = TeslaBrowserFetcher(config)
jobs = fetcher.safe_fetch()
```

### Option 2: Selenium with Undetected ChromeDriver

Even more reliable for bypassing detection.

#### Installation

```bash
pip install undetected-chromedriver selenium
```

#### Example Script

Create `scripts/tesla_selenium.py`:

```python
#!/usr/bin/env python3
"""Fetch Tesla jobs using Selenium with undetected ChromeDriver."""

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import json
import sys

sys.path.insert(0, ".")
from models import Job

def fetch_tesla_jobs():
    """Fetch Tesla jobs with Selenium."""

    options = uc.ChromeOptions()
    # Remove headless for first run to see what's happening
    # options.add_argument('--headless')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--no-sandbox')

    driver = uc.Chrome(options=options)

    try:
        print("Navigating to Tesla careers...")
        driver.get('https://www.tesla.com/careers/search')

        # Wait for page to load
        time.sleep(5)

        # Wait for job listings
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href*="careers"]'))
            )
        except:
            print("Warning: Job listings may not have loaded")

        # Extract job links
        job_links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="careers"]')

        jobs = []
        for link in job_links[:50]:  # Limit to first 50
            try:
                url = link.get_attribute('href')
                title = link.text.strip()

                if not title or len(title) < 5:
                    continue

                jobs.append({
                    'title': title,
                    'url': url,
                    'company': 'Tesla'
                })
            except:
                continue

        return jobs

    finally:
        driver.quit()

if __name__ == "__main__":
    jobs = fetch_tesla_jobs()

    print(f"\nFound {len(jobs)} jobs:")
    for job in jobs[:10]:
        print(f"- {job['title']}")
        print(f"  {job['url']}\n")

    # Save to file
    with open('tesla_jobs.json', 'w') as f:
        json.dump(jobs, f, indent=2)

    print(f"Saved to tesla_jobs.json")
```

Run:

```bash
python3 scripts/tesla_selenium.py
```

### Option 3: Manual Job Monitoring

Use Tesla's built-in job alerts and forward to Discord.

#### Setup

1. **Subscribe to Tesla Job Alerts**
   - Go to https://www.tesla.com/careers
   - Sign up for email alerts
   - Filter by "Software Engineer" and "United States"

2. **Create Email Parser**

Create `scripts/tesla_email_parser.py`:

```python
#!/usr/bin/env python3
"""Parse Tesla job alert emails and post to Discord."""

import imaplib
import email
import re
import os
import requests
from datetime import datetime

IMAP_SERVER = "imap.gmail.com"
EMAIL = os.environ.get("EMAIL_ADDRESS")
PASSWORD = os.environ.get("EMAIL_PASSWORD")
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_TESLA")

def parse_tesla_emails():
    """Check email for Tesla job alerts."""

    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL, PASSWORD)
    mail.select('inbox')

    # Search for unread Tesla emails
    _, messages = mail.search(None, '(UNSEEN FROM "tesla.com")')

    jobs = []
    for msg_num in messages[0].split():
        _, msg_data = mail.fetch(msg_num, '(RFC822)')
        email_body = msg_data[0][1]
        email_message = email.message_from_bytes(email_body)

        # Extract job information from email
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/html":
                    body = part.get_payload(decode=True).decode()
                    jobs.extend(extract_jobs_from_html(body))

    mail.close()
    mail.logout()

    return jobs

def extract_jobs_from_html(html):
    """Extract job URLs and titles from email HTML."""
    jobs = []

    # Find job links in email
    pattern = r'href="(https://[^"]*tesla\.com/careers[^"]*)"[^>]*>([^<]+)</a>'
    matches = re.findall(pattern, html)

    for url, title in matches:
        if title and len(title) > 5:
            jobs.append({
                'title': title.strip(),
                'url': url,
                'company': 'Tesla'
            })

    return jobs

def post_to_discord(jobs):
    """Post jobs to Discord webhook."""
    if not DISCORD_WEBHOOK:
        print("No webhook configured")
        return

    for job in jobs:
        payload = {
            "embeds": [{
                "title": job['title'],
                "url": job['url'],
                "color": 0xCC0000,  # Tesla red
                "fields": [
                    {"name": "Company", "value": job['company'], "inline": True},
                ],
                "timestamp": datetime.utcnow().isoformat()
            }]
        }

        response = requests.post(DISCORD_WEBHOOK, json=payload)
        if response.status_code != 204:
            print(f"Failed to post job: {response.status_code}")

if __name__ == "__main__":
    jobs = parse_tesla_emails()
    print(f"Found {len(jobs)} new jobs")

    if jobs:
        post_to_discord(jobs)
        print("Posted to Discord")
```

3. **Set up as Cron Job**

```bash
# Run every hour
0 * * * * cd /path/to/job-notification-discord && python3 scripts/tesla_email_parser.py
```

### Option 4: Third-Party Job Aggregators

Use existing job board APIs that already scrape Tesla.

#### LinkedIn Jobs API

```python
# Requires LinkedIn Partner API access
import requests

def fetch_tesla_from_linkedin():
    """Fetch Tesla jobs from LinkedIn."""

    # Note: Requires API credentials
    headers = {
        'Authorization': f'Bearer {LINKEDIN_ACCESS_TOKEN}',
    }

    params = {
        'keywords': 'Software Engineer',
        'companies': 'Tesla',
        'location': 'United States',
    }

    response = requests.get(
        'https://api.linkedin.com/v2/jobSearch',
        headers=headers,
        params=params
    )

    return response.json()
```

#### Indeed API

```python
import requests

def fetch_tesla_from_indeed():
    """Fetch Tesla jobs from Indeed."""

    params = {
        'q': 'Software Engineer',
        'l': 'United States',
        'co': 'US',
        'cmp': 'Tesla',
    }

    # Note: Indeed Publisher API requires partnership
    response = requests.get(
        'https://api.indeed.com/ads/apisearch',
        params=params
    )

    return response.json()
```

## Advanced Configuration

### Multi-Strategy Setup

Run both direct and browser methods:

```json
{
  "sources": {
    "tesla_api": {
      "fetcher": "tesla",
      "name": "Tesla API",
      "company": "Tesla",
      "use_api": true,
      "max_pages": 10
    },
    "tesla_browser": {
      "fetcher": "tesla_browser",
      "name": "Tesla Browser",
      "company": "Tesla",
      "headless": true,
      "max_jobs": 50,
      "poll_interval_seconds": 3600,
      "filter_keywords": [
        "software",
        "engineer",
        "developer"
      ]
    }
  }
}
```

### Keyword Filtering

Focus on specific roles:

```json
{
  "filter_keywords": [
    "software engineer",
    "software developer",
    "swe",
    "new grad",
    "university grad",
    "recent graduate",
    "entry level",
    "junior engineer",
    "intern",
    "internship",
    "co-op",
    "machine learning",
    "ml engineer",
    "ai engineer",
    "backend",
    "frontend",
    "full stack",
    "data engineer"
  ]
}
```

### Location Filtering

Add to your main filtering config:

```json
{
  "filtering": {
    "location": {
      "enabled": true,
      "allowed_keywords": [
        "palo alto",
        "fremont",
        "california",
        "austin",
        "texas",
        "nevada",
        "remote"
      ]
    }
  }
}
```

## Integration with Existing System

### Add to Main Registry

Edit `main.py` to include browser fetcher:

```python
# Add import
from fetchers.tesla_browser import TeslaBrowserFetcher

# Add to registry
FETCHER_REGISTRY = {
    # ... existing fetchers ...
    "tesla": TeslaFetcher,
    "tesla_browser": TeslaBrowserFetcher,
}
```

### State Management

The fetcher automatically tracks seen jobs via UID:

```python
from state import StateStore

state = StateStore("state.json")
fetcher = TeslaFetcher(config)

jobs = fetcher.safe_fetch()
new_jobs = [j for j in jobs if not state.has_seen(j.uid)]

for job in new_jobs:
    state.mark_seen(job.uid)
    # Post to Discord...

state.persist()
```

## Monitoring and Debugging

### Enable Debug Logging

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Run fetcher
fetcher = TeslaFetcher(config)
jobs = fetcher.safe_fetch()
```

### Check for Blocks

```python
from fetchers.tesla import TeslaFetcher
import requests

try:
    resp = requests.get(
        "https://cho.tbe.taleo.net/cho01/ats/careers/jobSearch.jsp?org=TESLA&cws=1"
    )

    if "Access Denied" in resp.text:
        print("❌ Blocked by Akamai")
    elif resp.status_code == 500:
        print("❌ Server error or maintenance")
    elif resp.status_code == 200:
        print("✅ Access successful")
    else:
        print(f"⚠️  Unexpected status: {resp.status_code}")

except Exception as e:
    print(f"❌ Error: {e}")
```

### Screenshot on Error

For browser mode:

```python
config = {
    "headless": False,  # Enable to see browser
    # ...
}

fetcher = TeslaBrowserFetcher(config)

try:
    jobs = fetcher.fetch()
except Exception as e:
    print(f"Error occurred: {e}")
    # Screenshots saved to tesla_error.png or tesla_timeout.png
```

## Performance Tips

### 1. Cache Results

```python
import json
from datetime import datetime, timedelta

CACHE_FILE = "tesla_jobs_cache.json"
CACHE_DURATION = timedelta(hours=1)

def get_cached_jobs():
    """Return cached jobs if still valid."""
    try:
        with open(CACHE_FILE) as f:
            data = json.load(f)

        cached_time = datetime.fromisoformat(data['timestamp'])
        if datetime.now() - cached_time < CACHE_DURATION:
            return data['jobs']
    except:
        pass

    return None

def cache_jobs(jobs):
    """Cache jobs with timestamp."""
    with open(CACHE_FILE, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'jobs': [j.dict() for j in jobs]
        }, f)
```

### 2. Rate Limiting

```python
import time
from datetime import datetime

last_fetch_time = {}

def should_fetch(source_name, min_interval_seconds=3600):
    """Check if enough time has passed since last fetch."""
    last_fetch = last_fetch_time.get(source_name)

    if not last_fetch:
        return True

    elapsed = time.time() - last_fetch
    return elapsed >= min_interval_seconds

# Use before fetching
if should_fetch("tesla", min_interval_seconds=3600):
    jobs = fetcher.safe_fetch()
    last_fetch_time["tesla"] = time.time()
```

### 3. Parallel Fetching

For browser mode with multiple searches:

```python
from concurrent.futures import ThreadPoolExecutor

def fetch_with_keyword(keyword):
    """Fetch jobs for specific keyword."""
    config = {
        "name": f"Tesla {keyword}",
        "company": "Tesla",
        "filter_keywords": [keyword]
    }
    fetcher = TeslaFetcher(config)
    return fetcher.safe_fetch()

keywords = ["software engineer", "data engineer", "ml engineer"]

with ThreadPoolExecutor(max_workers=3) as executor:
    results = executor.map(fetch_with_keyword, keywords)
    all_jobs = [job for jobs in results for job in jobs]
```

## Troubleshooting

### Problem: No jobs returned

**Solutions**:
1. Check if blocked: Look for "Access Denied" in logs
2. Try browser automation mode
3. Test from different IP address
4. Check Tesla careers site manually
5. Verify configuration is correct

### Problem: Browser automation fails

**Solutions**:
1. Update Playwright: `pip install -U playwright && playwright install`
2. Try non-headless mode to see what's happening
3. Increase timeout value
4. Check for CAPTCHA on page
5. Try Selenium with undetected-chromedriver

### Problem: Too many duplicate jobs

**Solutions**:
1. Ensure state.json is being persisted
2. Check UID generation is working
3. Verify state.has_seen() is being called
4. Look for URL normalization issues

### Problem: Missing jobs

**Solutions**:
1. Relax filter_keywords
2. Increase max_pages or max_jobs
3. Check pagination is working
4. Verify job extraction selectors

## Next Steps

1. Choose your fetching strategy (browser automation recommended)
2. Set up configuration
3. Test with small limits first
4. Monitor for blocks
5. Adjust polling frequency
6. Set up monitoring/alerting

For more details, see [TESLA_FETCHER_README.md](TESLA_FETCHER_README.md).
