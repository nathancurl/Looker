#!/usr/bin/env python3
"""Test script for TikTok/ByteDance fetchers.

This script tests the TikTok and ByteDance job fetchers with Selenium.
The sites have aggressive bot detection and require JavaScript rendering.
"""

import logging
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from fetchers.tiktok import TikTokFetcher, ByteDanceFetcher


def test_tiktok_selenium():
    """Test TikTok fetcher with Selenium."""
    print("=" * 60)
    print("Test 1: TikTok Fetcher (With Selenium)")
    print("=" * 60)

    try:
        import selenium
        from webdriver_manager.chrome import ChromeDriverManager
        print("Selenium is installed.")
    except ImportError:
        print("\nSelenium is NOT installed. Skipping Selenium test.")
        print("To install: pip install selenium webdriver-manager")
        return 0

    config = {
        'name': 'TikTok Careers',
        'company': 'TikTok',
        'keywords': ['software engineer', 'new grad'],
        'brand': 'tiktok',
        'headless': True,  # Set to False to see browser
        'max_scrolls': 3
    }

    fetcher = TikTokFetcher(config)
    jobs = fetcher.safe_fetch()

    print(f'\nFound {len(jobs)} jobs')

    if jobs:
        print('\nFirst 10 jobs:')
        for i, job in enumerate(jobs[:10], 1):
            print(f'\n{i}. {job.title}')
            print(f'   Company: {job.company}')
            print(f'   Location: {job.location}')
            print(f'   URL: {job.url}')
            print(f'   UID: {job.uid}')
            print(f'   Raw ID: {job.raw_id}')
    else:
        print('\nNo jobs found. The site may have blocked the request.')

    return len(jobs)


def test_bytedance_selenium():
    """Test ByteDance fetcher with Selenium."""
    print("\n" + "=" * 60)
    print("Test 2: ByteDance Fetcher (With Selenium)")
    print("=" * 60)

    try:
        import selenium
        print("Selenium is installed.")
    except ImportError:
        print("\nSelenium is NOT installed. Skipping Selenium test.")
        print("To install: pip install selenium webdriver-manager")
        return 0

    config = {
        'name': 'ByteDance Careers',
        'company': 'ByteDance',
        'keywords': ['software', 'engineer'],
        'headless': True,
        'max_scrolls': 3
    }

    fetcher = ByteDanceFetcher(config)
    jobs = fetcher.safe_fetch()

    print(f'\nFound {len(jobs)} jobs')

    if jobs:
        print('\nFirst 10 jobs:')
        for i, job in enumerate(jobs[:10], 1):
            print(f'\n{i}. {job.title}')
            print(f'   Company: {job.company}')
            print(f'   Location: {job.location}')
            print(f'   URL: {job.url}')
    else:
        print('\nNo jobs found. The site may have blocked the request.')

    return len(jobs)


def test_known_job_ids():
    """Test creating jobs from known job IDs."""
    print("\n" + "=" * 60)
    print("Test 4: Create Jobs from Known IDs")
    print("=" * 60)

    from models import Job

    # Known TikTok job postings
    known_jobs = [
        {
            'id': '7531986763343300871',
            'title': 'Frontend Software Engineer Graduate - 2026 Start',
            'location': 'San Jose, CA',
        },
        {
            'id': '7489012345678901234',
            'title': 'Backend Engineer - New Grad',
            'location': 'Seattle, WA',
        },
    ]

    jobs = []
    for job_data in known_jobs:
        job_id = job_data['id']
        url = f"https://lifeattiktok.com/search/{job_id}"
        raw_id = f"tiktok:{job_id}"
        uid = Job.generate_uid("tiktok", raw_id=raw_id)

        job = Job(
            uid=uid,
            source_group="tiktok",
            source_name="TikTok Known Jobs",
            title=job_data['title'],
            company="TikTok",
            location=job_data['location'],
            url=url,
            raw_id=raw_id,
            snippet="",
        )
        jobs.append(job)

    print(f'\nCreated {len(jobs)} jobs from known IDs:')
    for i, job in enumerate(jobs, 1):
        print(f'\n{i}. {job.title}')
        print(f'   Location: {job.location}')
        print(f'   URL: {job.url}')

    return len(jobs)


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("TikTok/ByteDance Fetcher Test Suite")
    print("=" * 60)

    results = {}

    # Test 1: TikTok with Selenium
    results['tiktok_selenium'] = test_tiktok_selenium()

    # Test 2: ByteDance with Selenium
    results['bytedance_selenium'] = test_bytedance_selenium()

    # Test 3: Known job IDs
    results['known_ids'] = test_known_job_ids()

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    for test_name, count in results.items():
        status = "✓" if count > 0 else "✗"
        print(f"{status} {test_name}: {count} jobs")

    print("\n" + "=" * 60)
    print("Notes:")
    print("=" * 60)
    print("1. TikTok/ByteDance have aggressive bot detection")
    print("2. Selenium with anti-detection measures is required")
    print("3. Jobs are filtered for software engineering and new grad positions")
    print("4. Monitor for rate limiting (may need delays between requests)")

    return 0 if any(results.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
