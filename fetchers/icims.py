"""Fetcher for iCIMS ATS portals via HTML scraping.

iCIMS career portals are server-rendered HTML pages. There is no JSON API.
We scrape the search results page to extract job listings.

Each job listing is delineated by a location header div:
    <div class="col-xs-6 header left"> → location
    <div class="col-xs-6 header right"> → posted date
    <div class="col-xs-12 title"> → <a><h3>Title</h3></a>
    <div class="col-xs-12 description"> → snippet
    <div class="col-xs-12 additionalFields"> → metadata

Pagination: ?pr=0, ?pr=1, etc. Page count in ".iCIMS_PagingBatch" links.
"""

import logging
import re
from datetime import datetime

from fetchers.base import BaseFetcher, resilient_get
from models import Job

logger = logging.getLogger(__name__)

SEARCH_PATH = "/jobs/search"
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class ICIMSFetcher(BaseFetcher):
    source_group = "icims"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._portal_url = source_config["portal_url"].rstrip("/")
        self._max_pages = source_config.get("max_pages", 10)

    def fetch(self) -> list[Job]:
        jobs = []
        page = 0

        while page < self._max_pages:
            url = f"{self._portal_url}{SEARCH_PATH}"
            params = {"ss": "1", "in_iframe": "1", "pr": str(page)}

            resp = resilient_get(
                url,
                params=params,
                headers={"Accept": "text/html", "User-Agent": BROWSER_UA},
                timeout=20,
            )
            resp.raise_for_status()

            html = resp.text
            page_jobs = self._parse_listings(html)

            if not page_jobs:
                break

            jobs.extend(page_jobs)

            total_pages = self._get_total_pages(html)
            if page + 1 >= total_pages:
                break
            page += 1

        return jobs

    def _parse_listings(self, html: str) -> list[Job]:
        """Parse job listings from iCIMS search results HTML."""
        jobs = []

        # Split by title divs - works across different iCIMS themes
        parts = re.split(r'<div[^>]*class="[^"]*col-xs-12 title[^"]*"[^>]*>', html)

        for i, part in enumerate(parts[1:], 1):
            # Include the preceding part for location/date context
            context_before = parts[i - 1] if i > 0 else ""
            job = self._parse_single_listing(part, context_before)
            if job:
                jobs.append(job)

        return jobs

    def _parse_single_listing(self, html_fragment: str, context_before: str = "") -> Job | None:
        """Parse a single job listing from an HTML fragment."""
        # Extract job URL, ID, and title - try both <a><h3> and <h3><a> patterns
        title_match = re.search(
            r'<a[^>]*href="([^"]*?/jobs/(\d+)/[^"]*?)"[^>]*>.*?<h[23][^>]*>\s*(.*?)\s*</h[23]>',
            html_fragment,
            re.DOTALL,
        )
        if not title_match:
            # Try the anchor-with-title-attr pattern (some iCIMS themes)
            title_match = re.search(
                r'<a[^>]*href="([^"]*?/jobs/(\d+)/[^"]*?)"[^>]*title="[^"]*?-\s*([^"]+)"',
                html_fragment,
            )
        if not title_match:
            return None

        job_url = title_match.group(1)
        raw_id = title_match.group(2)
        title = _strip_html(title_match.group(3)).strip()
        # Remove "Job Title" prefix that iCIMS adds via sr-only label
        title = re.sub(r"^Job Title\s*", "", title).strip()

        if not title:
            return None

        # Clean URL: remove in_iframe parameter
        job_url = re.sub(r"[?&]in_iframe=1", "", job_url)
        job_url = job_url.rstrip("?")

        # Combine context for location/date extraction
        full_context = context_before + html_fragment

        # Extract location from either the current fragment or preceding context
        location = ""
        loc_match = re.search(
            r'field-label">Job Locations</span>\s*<span[^>]*>\s*([^<]+)',
            full_context,
        )
        if loc_match:
            location = loc_match.group(1).strip()

        # Extract posted date from title attribute
        posted_at = None
        date_match = re.search(
            r'field-label">Posted Date</span>\s*<span[^>]*title="([^"]+)"',
            full_context,
        )
        if date_match:
            date_str = date_match.group(1).strip()
            try:
                posted_at = datetime.strptime(date_str, "%m/%d/%Y %I:%M %p")
            except (ValueError, AttributeError):
                pass

        # Extract description snippet
        snippet = ""
        desc_match = re.search(
            r'<div[^>]*class="[^"]*description[^"]*"[^>]*>(.*?)</div>',
            html_fragment,
            re.DOTALL,
        )
        if desc_match:
            snippet = _strip_html(desc_match.group(1))

        # Extract category from additionalFields
        tags = []
        cat_match = re.search(
            r"<dt[^>]*>Category</dt>\s*<dd[^>]*><span[^>]*>\s*([^<]+)",
            html_fragment,
        )
        if cat_match:
            tags.append(cat_match.group(1).strip())

        uid = Job.generate_uid(self.source_group, raw_id=raw_id)

        return Job(
            uid=uid,
            source_group=self.source_group,
            source_name=self.source_name,
            title=title,
            company=self._config.get("company", ""),
            location=location,
            url=job_url,
            snippet=snippet,
            posted_at=posted_at,
            raw_id=raw_id,
            tags=tags,
        )

    def _get_total_pages(self, html: str) -> int:
        """Extract total number of pages from pagination links."""
        pages = re.findall(r"of (\d+)", html)
        if pages:
            return max(int(p) for p in pages)

        page_links = re.findall(r"pr=(\d+)", html)
        if page_links:
            return max(int(p) for p in page_links) + 1

        return 1


def _strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
