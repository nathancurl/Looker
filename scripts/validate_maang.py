#!/usr/bin/env python3
"""Validate MAANG/singleton sources."""

import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from fetchers.base import USER_AGENT

TIMEOUT = 60
HEADERS = {"User-Agent": USER_AGENT}


def test_google():
    """Test Google XML feed."""
    url = "https://www.google.com/about/careers/applications/jobs/feed.xml"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 200:
            # Check it's XML
            if b"<jobs>" in resp.content or b"<item>" in resp.content:
                size_mb = len(resp.content) / (1024 * 1024)
                return True, f"OK ({size_mb:.1f} MB XML)"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)[:50]


def test_amazon():
    """Test Amazon Jobs API."""
    url = "https://www.amazon.jobs/en/search.json"
    try:
        resp = requests.get(url, params={"result_limit": 1}, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            total = data.get("hits", 0)
            return True, f"OK ({total} total jobs)"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)[:50]


def test_microsoft():
    """Test Microsoft Careers API."""
    url = "https://gcsservices.careers.microsoft.com/search/api/v1/search"
    try:
        resp = requests.get(url, params={"pg": 1, "pgSz": 1}, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            total = data.get("operationResult", {}).get("result", {}).get("totalJobs", 0)
            return True, f"OK ({total} total jobs)"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)[:50]


def test_netflix():
    """Test Netflix Jobs API (Eightfold platform)."""
    url = "https://explore.jobs.netflix.net/api/apply/v2/jobs"
    try:
        resp = requests.get(
            url,
            params={"domain": "netflix.com", "start": 0, "num": 10},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            total = data.get("count", 0)
            return True, f"OK ({total} total jobs)"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)[:50]


def test_apple():
    """Test Apple Jobs (HTML scraping)."""
    import re
    url = "https://jobs.apple.com/en-us/search"
    try:
        resp = requests.get(
            url,
            params={"location": "united-states-USA"},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}"

        # Look for job detail links in HTML
        pattern = r'/en-us/details/(\d+(?:-\d+)?)/([^"?/]+)'
        matches = re.findall(pattern, resp.text)
        unique_ids = set(m[0] for m in matches if "locationPicker" not in m[1])

        if unique_ids:
            return True, f"OK ({len(unique_ids)} jobs on page 1)"
        return False, "No job links found in HTML"
    except Exception as e:
        return False, str(e)[:50]


def test_meta():
    """Test Meta Jobs (best-effort GraphQL)."""
    config_path = Path(__file__).parent.parent / "config.json"
    with open(config_path) as f:
        config = json.load(f)

    doc_id = config.get("sources", {}).get("meta", {}).get("doc_id", "")
    if not doc_id:
        return False, "No doc_id configured"

    session = requests.Session()
    session.headers.update(HEADERS)

    # Step 1: Get LSD token from careers page
    try:
        page_resp = session.get("https://www.metacareers.com/jobs", timeout=TIMEOUT)
        if page_resp.status_code != 200:
            return False, f"Page HTTP {page_resp.status_code}"

        import re
        match = re.search(r'name="lsd"\s+value="([^"]+)"', page_resp.text)
        if not match:
            match = re.search(r'"LSD"\s*,\s*\[\]\s*,\s*\{"token"\s*:\s*"([^"]+)"', page_resp.text)
        if not match:
            return False, "Could not find LSD token"
        lsd_token = match.group(1)
    except Exception as e:
        return False, f"Page: {str(e)[:30]}"

    # Step 2: GraphQL query
    try:
        gql_resp = session.post(
            "https://www.metacareers.com/api/graphql/",
            data={
                "doc_id": doc_id,
                "variables": '{"search_input": {"q": "", "cursor": null}}',
                "lsd": lsd_token,
            },
            headers={"X-FB-LSD": lsd_token},
            timeout=TIMEOUT,
        )
        if gql_resp.status_code == 200:
            data = gql_resp.json()
            # Handle both response structures
            results = data.get("data", {}).get("job_search_with_featured_jobs", {}).get("all_jobs", [])
            if not results:
                results = data.get("data", {}).get("job_search", {}).get("results", [])
            return True, f"OK ({len(results)} jobs in first page)"
        return False, f"GraphQL HTTP {gql_resp.status_code}"
    except Exception as e:
        return False, f"GraphQL: {str(e)[:30]}"


def test_hn_hiring():
    """Test HN Who is Hiring RSS feed."""
    url = "https://hnrss.org/whoishiring/jobs"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 200:
            if b"<item>" in resp.content:
                items = resp.content.count(b"<item>")
                return True, f"OK ({items} items)"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)[:50]


def main():
    print("=" * 60)
    print("VALIDATING MAANG & SINGLETON SOURCES")
    print("=" * 60)

    tests = [
        ("Google", test_google),
        ("Amazon", test_amazon),
        ("Microsoft", test_microsoft),
        ("Netflix", test_netflix),
        ("Apple", test_apple),
        ("Meta", test_meta),
        ("HN Hiring", test_hn_hiring),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        ok, msg = test_fn()
        status = "✓" if ok else "✗"
        print(f"  {status} {name}: {msg}")
        if ok:
            passed += 1
        else:
            failed += 1

    print("\n" + "=" * 60)
    print(f"SUMMARY: {passed} passed, {failed} failed")
    print("=" * 60)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
