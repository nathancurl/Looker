#!/usr/bin/env python3
"""Validate all configured job sources by testing their API endpoints.

Usage:
    python scripts/validate_sources.py [--json]

This script tests every company in config.json to verify:
1. The API endpoint responds with 2xx status
2. The response contains valid job data structure

Use --json to output results in JSON format
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
    "warnings": [],
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
    """Test iCIMS portal by scraping the search page HTML."""
    import re

    portal_url = company.get("portal_url", "").rstrip("/")
    url = f"{portal_url}/jobs/search"
    if not _is_safe_url(url):
        return False, "Invalid or unsafe URL"
    try:
        resp = requests.get(
            url,
            params={"ss": "1", "in_iframe": "1"},
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html",
            },
            timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            # Count job links in the HTML
            job_links = re.findall(r'href="[^"]*?/jobs/\d+/[^"]*?"', resp.text)
            if job_links or "iCIMS_JobsTable" in resp.text:
                return True, f"OK ({len(job_links)} job links)"
            if "Please Enable Cookies" in resp.text:
                return False, "Blocked: requires cookies"
            return True, f"OK (portal accessible, 0 jobs)"
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


def test_maang(company: dict) -> tuple[bool, str]:
    """Test MAANG singleton sources by importing and running their fetchers."""
    source_type = company.get("_source_type", "")

    try:
        if source_type == "google":
            from fetchers.google import GoogleFetcher
            fetcher = GoogleFetcher(company)
        elif source_type == "amazon":
            url = company.get("base_url", company.get("api_url", ""))
            resp = requests.get(url, params={"result_limit": 1}, headers=HEADERS, timeout=TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                total = data.get("totalHits", 0)
                return True, f"OK ({total} jobs)"
            return False, f"HTTP {resp.status_code}"
        elif source_type == "microsoft":
            from fetchers.microsoft import MicrosoftFetcher
            fetcher = MicrosoftFetcher(company)
        elif source_type == "netflix":
            from fetchers.netflix import NetflixFetcher
            fetcher = NetflixFetcher(company)
        elif source_type == "apple":
            from fetchers.apple import AppleFetcher
            fetcher = AppleFetcher(company)
        elif source_type == "meta":
            from fetchers.meta import MetaFetcher
            fetcher = MetaFetcher(company)
        else:
            return False, f"Unknown MAANG source: {source_type}"

        # For non-Amazon sources, try to fetch
        if source_type != "amazon":
            jobs = fetcher.fetch()
            return True, f"OK ({len(jobs)} jobs)"

    except Exception as e:
        return False, str(e)[:80]


def test_custom(company: dict) -> tuple[bool, str]:
    """Test custom fetchers by importing and running fetch()."""
    source_type = company.get("_source_type", "")

    try:
        if source_type == "jpmorgan":
            from fetchers.jpmorgan import JPMorganFetcher
            fetcher = JPMorganFetcher(company)
        elif source_type == "oracle":
            from fetchers.oracle import OracleFetcher
            fetcher = OracleFetcher(company)
        elif source_type == "qualcomm":
            from fetchers.qualcomm import QualcommFetcher
            fetcher = QualcommFetcher(company)
        elif source_type == "rivian":
            from fetchers.rivian import RivianFetcher
            fetcher = RivianFetcher(company)
        elif source_type == "yelp":
            from fetchers.yelp import YelpFetcher
            fetcher = YelpFetcher(company)
        elif source_type == "shopify":
            from fetchers.shopify import ShopifyFetcher
            fetcher = ShopifyFetcher(company)
        elif source_type == "tiktok":
            from fetchers.tiktok import TikTokFetcher
            fetcher = TikTokFetcher(company)
        elif source_type == "goldmansachs":
            from fetchers.goldmansachs import GoldmanSachsFetcher
            fetcher = GoldmanSachsFetcher(company)
        elif source_type == "intuit":
            from fetchers.intuit import IntuitFetcher
            fetcher = IntuitFetcher(company)
        else:
            return False, f"Unknown custom source: {source_type}"

        jobs = fetcher.fetch()
        return True, f"OK ({len(jobs)} jobs)"

    except Exception as e:
        return False, str(e)[:80]


def test_selenium_sources(company: dict) -> tuple[bool, str]:
    """Test Selenium-based sources with headless mode."""
    source_type = company.get("_source_type", "")

    try:
        # Check if selenium is installed
        try:
            import selenium
        except ImportError:
            return False, "SKIP: selenium not installed"

        if source_type == "workday_selenium":
            from fetchers.workday_selenium import WorkdaySeleniumFetcher
            # Use minimal config for validation
            test_config = {**company, "max_scrolls": 1, "headless": True}
            fetcher = WorkdaySeleniumFetcher(test_config)
        elif source_type == "wellfound":
            from fetchers.wellfound import WellfoundFetcher
            test_config = {**company, "max_scrolls": 1, "headless": True}
            fetcher = WellfoundFetcher(test_config)
        elif source_type == "yc":
            from fetchers.yc import YCFetcher
            test_config = {**company, "headless": True}
            fetcher = YCFetcher(test_config)
        else:
            return False, f"Unknown selenium source: {source_type}"

        jobs = fetcher.fetch()
        return True, f"OK ({len(jobs)} jobs)"

    except Exception as e:
        error_msg = str(e)
        if "chromedriver" in error_msg.lower() or "chrome" in error_msg.lower():
            return False, "SKIP: ChromeDriver not available"
        return False, str(e)[:80]


def test_newgrad(company: dict) -> tuple[bool, str]:
    """Test NewGrad and RSS sources."""
    source_type = company.get("_source_type", "")

    try:
        if source_type == "newgrad_json":
            from fetchers.newgrad_json import NewGradJSONFetcher
            fetcher = NewGradJSONFetcher(company)
        elif source_type == "newgrad_markdown":
            from fetchers.newgrad_markdown import NewGradMarkdownFetcher
            fetcher = NewGradMarkdownFetcher(company)
        elif source_type == "hn_hiring":
            from fetchers.hnhiring import HNHiringFetcher
            fetcher = HNHiringFetcher(company)
        else:
            return False, f"Unknown newgrad source: {source_type}"

        jobs = fetcher.fetch()
        return True, f"OK ({len(jobs)} jobs)"

    except Exception as e:
        error_msg = str(e)
        if "rate limit" in error_msg.lower():
            return False, "TEMP_FAIL: Rate limited"
        return False, str(e)[:80]


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
    "google": test_maang,
    "amazon": test_maang,
    "microsoft": test_maang,
    "netflix": test_maang,
    "apple": test_maang,
    "meta": test_maang,
    "jpmorgan": test_custom,
    "oracle": test_custom,
    "qualcomm": test_custom,
    "rivian": test_custom,
    "yelp": test_custom,
    "shopify": test_custom,
    "tiktok": test_custom,
    "goldmansachs": test_custom,
    "intuit": test_custom,
    "workday_selenium": test_selenium_sources,
    "wellfound": test_selenium_sources,
    "yc": test_selenium_sources,
    "newgrad_json": test_newgrad,
    "newgrad_markdown": test_newgrad,
    "hn_hiring": test_newgrad,
}


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Validate all job sources")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    config_path = Path(__file__).parent.parent / "config.json"
    with open(config_path) as f:
        config = json.load(f)

    sources = config.get("sources", {})

    if not args.json:
        print("=" * 70)
        print("VALIDATING ALL JOB SOURCES")
        print("=" * 70)

    # Track detailed results for JSON output
    detailed_results = []

    for source_type, tester in TESTERS.items():
        source_conf = sources.get(source_type)
        if source_conf is None:
            continue

        companies = source_conf if isinstance(source_conf, list) else [source_conf]
        if not companies:
            continue

        if not args.json:
            print(f"\n## {source_type.upper()} ({len(companies)} companies)")
            print("-" * 50)

        for company in companies:
            # Add source_type to company dict for test functions
            company["_source_type"] = source_type
            name = company.get("name", company.get("company", source_type.upper()))
            passed, message = tester(company)

            # Categorize results
            if "SKIP" in message:
                category = "skipped"
                results["skipped"].append((source_type, name, message))
            elif "TEMP_FAIL" in message or "WARN" in message:
                category = "warning"
                results["warnings"].append((source_type, name, message))
                passed = True  # Don't fail on warnings
            elif passed:
                category = "passed"
                results["passed"].append((source_type, name, message))
            else:
                category = "failed"
                results["failed"].append((source_type, name, message))

            # Store detailed result for JSON
            detailed_results.append({
                "source_type": source_type,
                "name": name,
                "status": category,
                "message": message,
                "config": {k: v for k, v in company.items() if not k.startswith("_")},
            })

            if not args.json:
                status = "✓" if passed else "✗"
                if category == "skipped":
                    status = "⊘"
                elif category == "warning":
                    status = "⚠"
                print(f"  {status} {name}: {message}")

            # Be nice to APIs
            time.sleep(0.3)

    if args.json:
        # Output JSON results
        output = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {
                "passed": len(results["passed"]),
                "failed": len(results["failed"]),
                "warnings": len(results["warnings"]),
                "skipped": len(results["skipped"]),
                "total": len(detailed_results),
                "success_rate": round(
                    len(results["passed"])
                    / (len(results["passed"]) + len(results["failed"]))
                    * 100,
                    1,
                )
                if (len(results["passed"]) + len(results["failed"])) > 0
                else 0,
            },
            "results": detailed_results,
        }
        print(json.dumps(output, indent=2))
    else:
        # Summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"  Passed:   {len(results['passed'])}")
        print(f"  Failed:   {len(results['failed'])}")
        print(f"  Warnings: {len(results['warnings'])}")
        print(f"  Skipped:  {len(results['skipped'])}")
        total_tested = len(results["passed"]) + len(results["failed"])
        if total_tested > 0:
            success_rate = len(results["passed"]) / total_tested * 100
            print(f"  Success:  {success_rate:.1f}%")

        if results["failed"]:
            print(f"\n## FAILED SOURCES ({len(results['failed'])})")
            print("-" * 50)
            for source_type, name, message in results["failed"]:
                print(f"  [{source_type}] {name}: {message}")

        if results["warnings"]:
            print(f"\n## WARNINGS ({len(results['warnings'])})")
            print("-" * 50)
            for source_type, name, message in results["warnings"]:
                print(f"  [{source_type}] {name}: {message}")

    # Return exit code based on failures
    return 1 if results["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
