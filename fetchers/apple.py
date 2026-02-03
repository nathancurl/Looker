"""Fetcher for Apple Jobs — HTML scraping approach."""

import logging
import re
from urllib.parse import urljoin

import requests

from fetchers.base import BaseFetcher, USER_AGENT, DEFAULT_TIMEOUT
from models import Job

logger = logging.getLogger(__name__)

BASE_URL = "https://jobs.apple.com"
SEARCH_URL = "https://jobs.apple.com/en-us/search"

# Team code to name mapping
TEAM_CODES = {
    "SFTWR": "Software and Services",
    "HRDWR": "Hardware",
    "MKTG": "Marketing",
    "OPMFG": "Operations and Supply Chain",
    "DESGN": "Design",
    "CRPRT": "Corporate Functions",
    "APPST": "Apple Store",
    "SPRT": "Support and Service",
    "MLAI": "Machine Learning and AI",
}


class AppleFetcher(BaseFetcher):
    source_group = "maang"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._max_pages = source_config.get("max_pages", 250)  # ~4500 US jobs

    def fetch(self) -> list[Job]:
        session = requests.Session()
        session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })

        jobs = []
        seen_ids = set()
        page = 1

        while page <= self._max_pages:
            try:
                params = {"location": "united-states-USA", "page": page}
                resp = session.get(SEARCH_URL, params=params, timeout=DEFAULT_TIMEOUT)
                resp.raise_for_status()
            except Exception as e:
                logger.warning("Apple: failed to fetch page %d: %s", page, e)
                break

            # Parse job links from HTML
            page_jobs = self._parse_jobs_from_html(resp.text, seen_ids)

            if not page_jobs:
                # No jobs on this page, we're done
                break

            jobs.extend(page_jobs)

            # Check if there's a next page link
            if not self._has_next_page(resp.text, page):
                break

            page += 1

        return jobs

    def _parse_jobs_from_html(self, html: str, seen_ids: set) -> list[Job]:
        """Extract job listings from HTML content."""
        jobs = []

        # Pattern: /en-us/details/{id}/{slug}?team={team}
        # ID can be like "200644589-0836" or "114438158"
        pattern = r'/en-us/details/(\d+(?:-\d+)?)/([^"?/]+)(?:\?team=(\w+))?'
        matches = re.findall(pattern, html)

        for job_id, slug, team_code in matches:
            # Skip duplicates and locationPicker links
            if job_id in seen_ids or "locationPicker" in slug:
                continue
            seen_ids.add(job_id)

            # Convert slug to title
            title = _slug_to_title(slug)

            # Get team name
            team_name = TEAM_CODES.get(team_code, team_code) if team_code else ""

            # Build URL
            url = f"{BASE_URL}/en-us/details/{job_id}/{slug}"
            if team_code:
                url += f"?team={team_code}"

            raw_id = f"apple:{job_id}"
            uid = Job.generate_uid(self.source_group, raw_id=raw_id)

            tags = [team_name] if team_name else []

            jobs.append(
                Job(
                    uid=uid,
                    source_group=self.source_group,
                    source_name=self.source_name,
                    title=title,
                    company=self._config.get("company", "Apple"),
                    location="United States",  # We're filtering to US
                    url=url,
                    raw_id=raw_id,
                    tags=tags,
                )
            )

        return jobs

    def _has_next_page(self, html: str, current_page: int) -> bool:
        """Check if there's a next page of results."""
        # Look for pagination links
        next_page = current_page + 1
        next_pattern = rf'[?&]page={next_page}["\']'
        return bool(re.search(next_pattern, html))


def _slug_to_title(slug: str) -> str:
    """Convert URL slug to readable title."""
    # Replace hyphens with spaces and title case
    title = slug.replace("-", " ")
    # Capitalize properly
    title = title.title()
    # Fix common abbreviations
    replacements = {
        " Swe ": " SWE ",
        " Soc ": " SoC ",
        " Os ": " OS ",
        " Ai ": " AI ",
        " Ml ": " ML ",
        " Qa ": " QA ",
        " Ui ": " UI ",
        " Ux ": " UX ",
        " Cpu ": " CPU ",
        " Gpu ": " GPU ",
        " Io ": " I/O ",
        " Hwe ": " HWE ",
        " Sr ": " Sr. ",
        " Siri ": " Siri ",  # Ensure Siri stays capitalized
    }
    for old, new in replacements.items():
        title = title.replace(old, new)
    return title.strip()
