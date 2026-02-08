#!/usr/bin/env python3
"""Test script for Workday Selenium fetcher."""

import logging
from fetchers.workday_selenium import WorkdaySeleniumFetcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Test configuration for Visa
test_config = {
    "name": "Visa",
    "company": "Visa",
    "base_url": "https://visa.wd5.myworkdayjobs.com/Visa_Careers",
    "max_pages": 2,  # Only test 2 pages for speed
    "headless": False,  # Set to True for production
}

print(f"\n{'='*60}")
print(f"Testing Workday Selenium Fetcher - {test_config['company']}")
print(f"{'='*60}\n")

fetcher = WorkdaySeleniumFetcher(test_config)
jobs = fetcher.fetch()

print(f"\n{'='*60}")
print(f"Results: Found {len(jobs)} jobs")
print(f"{'='*60}\n")

if jobs:
    print("Sample jobs:")
    for job in jobs[:5]:  # Show first 5 jobs
        print(f"\n  Title: {job.title}")
        print(f"  Company: {job.company}")
        print(f"  Location: {job.location}")
        print(f"  URL: {job.url}")
        if job.posted_at:
            print(f"  Posted: {job.posted_at}")
        print(f"  UID: {job.uid}")
else:
    print("No jobs found!")
