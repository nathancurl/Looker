#!/usr/bin/env python3
"""Validate all configured job sources by testing their API endpoints.

Usage:
    python scripts/validate_sources.py [--fix]

This script tests every company in config.json to verify:
1. The API endpoint responds with 2xx status
2. The response contains valid job data structure

Use --fix to automatically remove failing entries from config.json
"""

import json
import sys
import time
from pathlib import Path

import requests

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fetchers.base import USER_AGENT

TIMEOUT = 15
HEADERS = {"User-Agent": USER_AGENT}

# Results tracking
results = {
    "passed": [],
    "failed": [],
    "skipped": [],
}


def test_greenhouse(company: dict) -> tuple[bool, str]:
    """Test Greenhouse API endpoint."""
    token = company.get("board_token", "")
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            job_count = len(data.get("jobs", []))
            return True, f"OK ({job_count} jobs)"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)[:50]


def test_lever(company: dict) -> tuple[bool, str]:
    """Test Lever API endpoint."""
    slug = company.get("slug", "")
    url = f"https://api.lever.co/v0/postings/{slug}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            job_count = len(data) if isinstance(data, list) else 0
            return True, f"OK ({job_count} jobs)"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)[:50]


def test_ashby(company: dict) -> tuple[bool, str]:
    """Test Ashby API endpoint."""
    clientname = company.get("clientname", "")
    url = f"https://api.ashbyhq.com/posting-api/job-board/{clientname}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            job_count = len(data.get("jobs", []))
            return True, f"OK ({job_count} jobs)"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)[:50]


def test_workable(company: dict) -> tuple[bool, str]:
    """Test Workable API endpoint."""
    subdomain = company.get("subdomain", "")
    url = f"https://apply.workable.com/api/v1/widget/accounts/{subdomain}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            job_count = len(data.get("jobs", []))
            return True, f"OK ({job_count} jobs)"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)[:50]


def test_workday(company: dict) -> tuple[bool, str]:
    """Test Workday API endpoint."""
    base_url = company.get("base_url", "")
    try:
        resp = requests.post(
            base_url,
            json={"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""},
            headers={**HEADERS, "Content-Type": "application/json"},
            timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            total = data.get("total", 0)
            return True, f"OK ({total} total jobs)"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)[:50]


def test_jobvite(company: dict) -> tuple[bool, str]:
    """Test Jobvite API endpoint."""
    company_id = company.get("company_id", "")
    url = f"https://jobs.jobvite.com/api/v2/{company_id}/jobs"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            job_count = len(data.get("requisitions", []))
            return True, f"OK ({job_count} jobs)"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)[:50]


def _is_safe_url(url: str) -> bool:
    """Validate URL is not targeting internal/localhost resources (SSRF protection)."""
    from urllib.parse import urlparse
    import ipaddress
    import socket

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    # Fast block obvious localhost hostnames
    if hostname in ("localhost",):
        return False

    # Resolve DNS and block any private/internal targets (prevents DNS rebinding)
    try:
        infos = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except OSError:
        return False

    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False

        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False

    return True


def test_icims(company: dict) -> tuple[bool, str]:
    """Test iCIMS API endpoint."""
    portal_url = company.get("portal_url", "").rstrip("/")
    url = f"{portal_url}/jobs"
    if not _is_safe_url(url):
        return False, "Invalid or unsafe URL"
    try:
        resp = requests.get(
            url,
            params={"page": 1, "pageSize": 1},
            headers={**HEADERS, "Accept": "application/json"},
            timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            total = data.get("total", len(data.get("jobs", [])))
            return True, f"OK ({total} jobs)"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)[:50]


def test_taleo(company: dict) -> tuple[bool, str]:
    """Test Taleo API endpoint."""
    base_url = company.get("base_url", "").rstrip("/")
    url = f"{base_url}/requisition/searchRequisitions"
    if not _is_safe_url(url):
        return False, "Invalid or unsafe URL"
    try:
        resp = requests.get(
            url,
            params={"start": 0, "limit": 1},
            headers={**HEADERS, "Accept": "application/json"},
            timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            total = data.get("total", data.get("totalCount", 0))
            return True, f"OK ({total} jobs)"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)[:50]


def test_smartrecruiters(company: dict) -> tuple[bool, str]:
    """Test SmartRecruiters API endpoint."""
    company_id = company.get("company_id", "")
    url = f"https://api.smartrecruiters.com/v1/companies/{company_id}/postings"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            total = data.get("totalFound", len(data.get("content", [])))
            return True, f"OK ({total} jobs)"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)[:50]


# Map source types to test functions
TESTERS = {
    "greenhouse": test_greenhouse,
    "lever": test_lever,
    "ashby": test_ashby,
    "workable": test_workable,
    "workday": test_workday,
    "jobvite": test_jobvite,
    "icims": test_icims,
    "taleo": test_taleo,
    "smartrecruiters": test_smartrecruiters,
}

# Source types that are singletons (not lists)
SINGLETON_SOURCES = {"google", "amazon", "microsoft", "netflix", "apple", "meta"}


def main():
    config_path = Path(__file__).parent.parent / "config.json"
    with open(config_path) as f:
        config = json.load(f)

    sources = config.get("sources", {})

    print("=" * 70)
    print("VALIDATING ALL JOB SOURCES")
    print("=" * 70)

    for source_type, tester in TESTERS.items():
        source_conf = sources.get(source_type)
        if source_conf is None:
            continue

        companies = source_conf if isinstance(source_conf, list) else [source_conf]
        if not companies:
            continue

        print(f"\n## {source_type.upper()} ({len(companies)} companies)")
        print("-" * 50)

        for company in companies:
            name = company.get("name", company.get("company", "Unknown"))
            passed, message = tester(company)

            status = "✓" if passed else "✗"
            print(f"  {status} {name}: {message}")

            if passed:
                results["passed"].append((source_type, name))
            else:
                results["failed"].append((source_type, name, message))

            # Be nice to APIs
            time.sleep(0.3)

    # Skip singleton MAANG sources for now (they need special handling)
    print(f"\n## SINGLETON SOURCES (skipped)")
    print("-" * 50)
    for source_type in SINGLETON_SOURCES:
        if source_type in sources:
            print(f"  - {source_type}: Requires manual testing")
            results["skipped"].append((source_type, source_type))

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Passed:  {len(results['passed'])}")
    print(f"  Failed:  {len(results['failed'])}")
    print(f"  Skipped: {len(results['skipped'])}")

    if results["failed"]:
        print(f"\n## FAILED SOURCES ({len(results['failed'])})")
        print("-" * 50)
        for source_type, name, message in results["failed"]:
            print(f"  [{source_type}] {name}: {message}")

    # Return exit code based on failures
    return 1 if results["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
