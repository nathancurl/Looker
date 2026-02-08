#!/usr/bin/env python3
"""Test script for Tesla fetcher."""

import logging
import sys

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from fetchers.tesla import TeslaFetcher

def main():
    """Test the Tesla fetcher."""
    print("=" * 80)
    print("Testing Tesla Fetcher with Selenium")
    print("=" * 80)

    # Create fetcher with config
    config = {
        "name": "tesla_test",
        "headless": True,  # Set to False to see the browser
        "max_scrolls": 3,  # Limit scrolls for testing
        "save_html": True,  # Save HTML for debugging
    }

    fetcher = TeslaFetcher(config)

    print("\nFetching jobs...")
    jobs = fetcher.fetch()

    print(f"\n{'=' * 80}")
    print(f"Found {len(jobs)} jobs total")
    print(f"{'=' * 80}\n")

    if jobs:
        # Display first 5 jobs
        print("First few jobs:")
        for i, job in enumerate(jobs[:5], 1):
            print(f"\n{i}. {job.title}")
            print(f"   Company: {job.company}")
            print(f"   Location: {job.location}")
            print(f"   URL: {job.url}")
            print(f"   UID: {job.uid}")
            print(f"   Raw ID: {job.raw_id}")
            if job.tags:
                print(f"   Tags: {', '.join(job.tags)}")

        if len(jobs) > 5:
            print(f"\n... and {len(jobs) - 5} more jobs")

        return 0
    else:
        print("No jobs found. This might indicate:")
        print("1. The page structure has changed")
        print("2. Bot detection is still blocking the request")
        print("3. No matching jobs are currently posted")
        print("\nTry setting headless=False to see what's happening in the browser.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
