#!/usr/bin/env python3
"""Test Tesla fetcher parsing logic with mock HTML."""

import sys
from fetchers.tesla import TeslaFetcher
from models import Job

# Mock HTML similar to what a Tesla/Taleo job board might contain
MOCK_HTML = """
<html>
<body>
<table class="jobs-table">
    <tbody>
        <tr class="job-row">
            <td class="title">
                <a href="/cho01/ats/careers/requisition.jsp?org=TESLA&cws=1&rid=12345">
                    Software Engineer, New Grad
                </a>
            </td>
            <td class="location">Palo Alto, CA</td>
        </tr>
        <tr class="job-row">
            <td class="title">
                <a href="/cho01/ats/careers/requisition.jsp?org=TESLA&cws=1&rid=12346">
                    Software Developer - University Grad
                </a>
            </td>
            <td class="location">Austin, TX</td>
        </tr>
        <tr class="job-row">
            <td class="title">
                <a href="/cho01/ats/careers/requisition.jsp?org=TESLA&cws=1&rid=12347">
                    Senior Mechanical Engineer
                </a>
            </td>
            <td class="location">Fremont, CA</td>
        </tr>
    </tbody>
</table>
</body>
</html>
"""

def main():
    """Test the Tesla fetcher parsing logic."""
    print("=" * 80)
    print("Testing Tesla Fetcher Parsing Logic")
    print("=" * 80)

    # Create fetcher
    config = {"name": "tesla_test"}
    fetcher = TeslaFetcher(config)

    # Test HTML parsing
    print("\nTesting HTML parsing with mock data...")
    jobs = fetcher._parse_jobs_from_html(MOCK_HTML)

    print(f"\nParsed {len(jobs)} jobs from mock HTML")

    if jobs:
        for i, job in enumerate(jobs, 1):
            print(f"\n{i}. {job.title}")
            print(f"   Company: {job.company}")
            print(f"   URL: {job.url}")
            print(f"   UID: {job.uid}")
            print(f"   Raw ID: {job.raw_id}")

        # Test filtering
        print("\n" + "=" * 80)
        print("Testing filter logic...")
        print("=" * 80)

        filtered_jobs = [job for job in jobs if fetcher._matches_filters(job)]
        print(f"\nFound {len(filtered_jobs)} matching jobs after filtering")

        for job in filtered_jobs:
            print(f"  - {job.title}")

        return 0
    else:
        print("ERROR: Failed to parse jobs from mock HTML")
        return 1

if __name__ == "__main__":
    sys.exit(main())
