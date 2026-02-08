#!/usr/bin/env python3
"""Test script for Tesla job fetcher.

This script demonstrates how to use the Tesla fetcher and tests
its functionality against the live Tesla Taleo API.

Note: Due to Tesla's aggressive anti-bot protection (Akamai),
direct API calls may be blocked. This test helps identify if
the protection is active and provides guidance on workarounds.
"""

import logging
import sys
from pprint import pprint

# Add parent directory to path for imports
sys.path.insert(0, ".")

from fetchers.tesla import TeslaFetcher

# Configure logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def test_api_mode():
    """Test fetcher using Taleo API mode."""
    print("\n" + "="*80)
    print("TEST 1: Fetching Tesla jobs via Taleo API")
    print("="*80)

    config = {
        "name": "Tesla",
        "company": "Tesla",
        "use_api": True,
        "max_pages": 2,  # Limit to 2 pages for testing
        "filter_keywords": [
            "software engineer",
            "software developer",
            "new grad",
            "university",
            "intern"
        ]
    }

    fetcher = TeslaFetcher(config)
    jobs = fetcher.safe_fetch()

    print(f"\nFetched {len(jobs)} jobs via API mode")

    if jobs:
        print("\nSample jobs:")
        for job in jobs[:5]:  # Show first 5 jobs
            print(f"\n- {job.title}")
            print(f"  Location: {job.location}")
            print(f"  URL: {job.url}")
            print(f"  Tags: {', '.join(job.tags) if job.tags else 'None'}")
            if job.snippet:
                print(f"  Snippet: {job.snippet[:100]}...")
    else:
        print("\n⚠️  No jobs fetched. This likely means:")
        print("   1. Tesla's Akamai protection blocked the request")
        print("   2. The API endpoint is down or changed")
        print("   3. Network/firewall issues")

    return jobs


def test_html_mode():
    """Test fetcher using HTML scraping mode."""
    print("\n" + "="*80)
    print("TEST 2: Fetching Tesla jobs via HTML scraping")
    print("="*80)

    config = {
        "name": "Tesla",
        "company": "Tesla",
        "use_api": False,  # Force HTML mode
        "max_pages": 2,
        "filter_keywords": []  # No filtering for this test
    }

    fetcher = TeslaFetcher(config)
    jobs = fetcher.safe_fetch()

    print(f"\nFetched {len(jobs)} jobs via HTML mode")

    if jobs:
        print("\nSample jobs:")
        for job in jobs[:5]:
            print(f"\n- {job.title}")
            print(f"  Location: {job.location}")
            print(f"  URL: {job.url}")
    else:
        print("\n⚠️  No jobs fetched. HTML scraping also blocked.")

    return jobs


def test_filtering():
    """Test keyword filtering functionality."""
    print("\n" + "="*80)
    print("TEST 3: Testing keyword filtering")
    print("="*80)

    config = {
        "name": "Tesla",
        "company": "Tesla",
        "use_api": True,
        "max_pages": 5,
        "filter_keywords": [
            "software",
            "engineer",
            "developer",
            "programmer"
        ]
    }

    fetcher = TeslaFetcher(config)
    jobs = fetcher.safe_fetch()

    print(f"\nFetched {len(jobs)} software engineering jobs")

    if jobs:
        print("\nFiltered job titles:")
        for job in jobs[:10]:
            print(f"  - {job.title}")
    else:
        print("\n⚠️  No jobs matched filters (or fetch was blocked)")

    return jobs


def test_direct_parsing():
    """Test job parsing with sample data."""
    print("\n" + "="*80)
    print("TEST 4: Testing job parsing with mock data")
    print("="*80)

    config = {
        "name": "Tesla",
        "company": "Tesla",
    }

    fetcher = TeslaFetcher(config)

    # Sample Taleo API response
    sample_job = {
        "requisitionId": "12345",
        "title": "Software Engineer, New Grad",
        "location": {
            "city": "Palo Alto",
            "state": "CA",
            "country": "United States"
        },
        "description": "<p>Join our team as a Software Engineer...</p>",
        "lastPublishedDate": 1706745600000,  # Epoch milliseconds
        "category": "Engineering",
        "department": "Software"
    }

    job = fetcher._parse_taleo_job(sample_job)

    if job:
        print("\n✓ Successfully parsed sample job:")
        print(f"  UID: {job.uid}")
        print(f"  Title: {job.title}")
        print(f"  Company: {job.company}")
        print(f"  Location: {job.location}")
        print(f"  URL: {job.url}")
        print(f"  Tags: {job.tags}")
        print(f"  Posted: {job.posted_at}")
    else:
        print("\n✗ Failed to parse sample job")

    return job


def print_summary():
    """Print summary and recommendations."""
    print("\n" + "="*80)
    print("SUMMARY & RECOMMENDATIONS")
    print("="*80)

    print("""
Tesla uses Oracle Taleo Business Edition with aggressive Akamai protection.
This makes automated job fetching challenging without additional measures.

RECOMMENDED APPROACHES:

1. Browser Automation (Most Reliable)
   - Use Selenium or Playwright with stealth plugins
   - Implement random delays between requests
   - Rotate user agents and implement cookie handling
   - Example libraries: undetected-chromedriver, playwright-stealth

2. Proxy Services
   - Use residential proxies to avoid detection
   - Services like Bright Data, Smartproxy, or Oxylabs
   - Rotate IPs between requests

3. Official API Access
   - Contact Tesla HR/recruiting for API access
   - Some large companies provide partner API access
   - May require business partnership or agreement

4. Alternative Data Sources
   - Job boards: LinkedIn, Indeed, Glassdoor
   - Use existing aggregator APIs that already have Tesla data
   - RSS feeds or email alerts from Tesla careers

5. Taleo REST API (If Access Granted)
   - Endpoint: https://cho.tbe.taleo.net/cho01/ats/careers/requisition/searchRequisitions
   - Requires proper authentication headers
   - May need to contact Oracle/Taleo for API credentials

CONFIGURATION EXAMPLE:

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
  }
}

TESTING NOTES:

- Test from different IP addresses to confirm blocking
- Monitor for CAPTCHA or "Access Denied" messages
- Check HTTP status codes (403, 429 indicate blocking)
- Implement exponential backoff on failures
""")


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("TESLA JOB FETCHER TEST SUITE")
    print("="*80)

    try:
        # Test 4: Direct parsing (always works)
        test_direct_parsing()

        # Test 1: API mode
        api_jobs = test_api_mode()

        # Test 2: HTML mode (if API failed)
        if not api_jobs:
            test_html_mode()

        # Test 3: Filtering
        test_filtering()

        # Print summary
        print_summary()

    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.exception("Test suite failed with error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
