"""Fetcher for Y Combinator Jobs via news.ycombinator.com/jobs."""

import logging
import re

import requests

from fetchers.base import BaseFetcher, USER_AGENT, DEFAULT_TIMEOUT
from models import Job

logger = logging.getLogger(__name__)

HN_JOBS_URL = "https://news.ycombinator.com/jobs"


class YCFetcher(BaseFetcher):
    source_group = "yc"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._max_pages = source_config.get("max_pages", 5)

    def fetch(self) -> list[Job]:
        session = requests.Session()
        session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })

        jobs = []
        seen_ids = set()
        url = HN_JOBS_URL

        for page in range(self._max_pages):
            try:
                resp = session.get(url, timeout=DEFAULT_TIMEOUT)
                resp.raise_for_status()
            except Exception as e:
                logger.warning("YC: failed to fetch page %d: %s", page + 1, e)
                break

            page_jobs = self._parse_jobs_from_html(resp.text, seen_ids)
            if not page_jobs:
                break

            jobs.extend(page_jobs)

            # Find "More" link for pagination
            more_match = re.search(r'<a href="([^"]+)" class="morelink"', resp.text)
            if not more_match:
                break
            url = f"https://news.ycombinator.com/{more_match.group(1)}"

        return jobs

    def _parse_jobs_from_html(self, html: str, seen_ids: set) -> list[Job]:
        """Extract job listings from HN jobs page."""
        jobs = []

        # Pattern: <tr class="athing submission" id="123">...<a href="URL">TITLE</a>
        pattern = (
            r'<tr class="athing submission" id="(\d+)"[^>]*>.*?'
            r'<span class="titleline">\s*<a href="([^"]+)">\s*([^<]+?)\s*</a>'
        )
        matches = re.findall(pattern, html, re.DOTALL)

        for hn_id, job_url, title in matches:
            if hn_id in seen_ids:
                continue
            seen_ids.add(hn_id)

            # Parse company and role from title
            # Format: "Company (YC Sxx) Is Hiring..." or "Company (YC Sxx) Is Hiring a Role"
            company, role = _parse_title(title)

            # Extract YC batch from title
            batch_match = re.search(r'\(YC ([A-Z]\d{2})\)', title)
            batch = batch_match.group(1) if batch_match else ""
            tags = [f"YC {batch}"] if batch else []

            raw_id = f"yc:{hn_id}"
            uid = Job.generate_uid(self.source_group, raw_id=raw_id)

            jobs.append(
                Job(
                    uid=uid,
                    source_group=self.source_group,
                    source_name=self.source_name,
                    title=role,
                    company=company,
                    url=job_url,
                    raw_id=raw_id,
                    tags=tags,
                )
            )

        return jobs


def _parse_title(title: str) -> tuple[str, str]:
    """Parse company name and role from HN job title.

    Examples:
    - "Clearspace (YC W23) Is Hiring an Applied Researcher (ML)"
    - "CollectWise (YC F24) Is Hiring"
    - "Insane Growth Goldbridge (YC F25) Is Hiring a Forward Deployed Engineer"
    """
    # Remove YC batch marker for cleaner parsing
    clean_title = re.sub(r'\s*\(YC [A-Z]\d{2}\)\s*', ' ', title).strip()

    # Common patterns
    patterns = [
        r'^(.+?)\s+Is Hiring\s+(?:an?\s+)?(.+)$',
        r'^(.+?)\s+Is Hiring$',
        r'^(.+?)\s*[-–]\s*(.+)$',
    ]

    for pattern in patterns:
        match = re.match(pattern, clean_title, re.IGNORECASE)
        if match:
            groups = match.groups()
            company = groups[0].strip()
            role = groups[1].strip() if len(groups) > 1 and groups[1] else "Engineering Role"
            return company, role

    # Fallback: use the whole title as company, generic role
    return clean_title, "Engineering Role"
