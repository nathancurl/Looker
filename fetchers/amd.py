"""Fetcher for AMD careers portal.

AMD uses a Jibe/iCIMS-powered careers site that provides a JSON API
at https://careers.amd.com/api/jobs. This is the same platform used by
Rivian and other companies. The API returns structured job data with
pagination support, making Selenium unnecessary.

API Structure:
- Base URL: https://careers.amd.com/api/jobs
- Pagination: ?page=1 (returns ~10 jobs per page, pageSize param ignored)
- Filtering: &categories=Engineering
- Response includes: jobs list (each with a nested data dict)
- Empty jobs array indicates end of results

Key Fields per job (inside data dict):
- slug / req_id: numeric job identifier
- title: job title
- city, state, country: location components
- location_name: combined location string
- apply_url: direct application link (points to icims portal)
- categories: list of dicts with "name" key
- posted_date: ISO 8601 date string
- description, qualifications: job details
- employment_type: e.g. "FULL_TIME"
- tags2-tags8: salary/compensation metadata
"""

import logging
import re
from datetime import datetime

from fetchers.base import BaseFetcher, resilient_get
from models import Job

logger = logging.getLogger(__name__)

AMD_API_URL = "https://careers.amd.com/api/jobs"
AMD_CAREERS_BASE = "https://careers.amd.com/careers-home/jobs"


class AMDFetcher(BaseFetcher):
    """Fetcher for AMD careers using their Jibe/iCIMS JSON API."""

    source_group = "amd"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._categories = source_config.get("categories", [])
        self._max_pages = source_config.get("max_pages", 200)
        # API returns ~10 jobs per page regardless of pageSize parameter
        self._page_size = 10

    def fetch(self) -> list[Job]:
        """Fetch jobs from AMD careers API.

        Iterates through categories (or fetches all if none specified),
        paginating until the API returns an empty jobs array.

        Returns:
            List of Job objects.
        """
        jobs = []

        if self._categories:
            for category in self._categories:
                jobs.extend(self._fetch_category(category))
        else:
            jobs.extend(self._fetch_category(None))

        return jobs

    def _fetch_category(self, category: str | None) -> list[Job]:
        """Fetch all jobs for a given category, handling pagination.

        Args:
            category: Category name (e.g. "Engineering") or None for all.

        Returns:
            List of Job objects.
        """
        jobs = []
        page = 1

        while page <= self._max_pages:
            params: dict = {"page": page}

            if category:
                params["categories"] = category
                logger.debug(
                    "AMD: fetching category=%s page=%d", category, page
                )
            else:
                logger.debug("AMD: fetching all jobs page=%d", page)

            resp = resilient_get(
                AMD_API_URL,
                params=params,
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

            job_list = data.get("jobs", [])
            if not job_list:
                logger.debug("AMD: empty page %d, stopping", page)
                break

            for item in job_list:
                job = self._parse_job(item)
                if job:
                    jobs.append(job)

            # If fewer than expected, likely the last page
            if len(job_list) < self._page_size:
                break

            page += 1

        return jobs

    def _parse_job(self, item: dict) -> Job | None:
        """Parse a single job entry from the API response.

        Args:
            item: A job dict from the API (contains a nested "data" dict).

        Returns:
            A Job object, or None if the entry cannot be parsed.
        """
        job_data = item.get("data", {})
        if not job_data:
            return None

        # Extract identifiers
        raw_id = str(job_data.get("req_id") or job_data.get("slug") or "")
        if not raw_id:
            return None

        title = job_data.get("title", "")
        if not title:
            return None

        # Build location string
        city = job_data.get("city", "")
        state = job_data.get("state", "")
        country = job_data.get("country", "")
        location_parts = [p for p in (city, state, country) if p]
        location = ", ".join(location_parts)

        # Get job URL -- prefer apply_url, fall back to careers page
        job_url = job_data.get("apply_url", "")
        if not job_url:
            job_url = f"{AMD_CAREERS_BASE}/{raw_id}"

        # Build a snippet from description or qualifications
        description = (
            job_data.get("description", "")
            or job_data.get("qualifications", "")
        )
        snippet = _strip_html(description)

        # Parse posted date
        posted_at = None
        posted_date = job_data.get("posted_date")
        if posted_date:
            try:
                posted_at = datetime.fromisoformat(
                    posted_date.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                pass

        # Extract category tags
        tags = []
        categories = job_data.get("categories", [])
        for cat in categories:
            if isinstance(cat, dict) and cat.get("name"):
                tags.append(cat["name"])
            elif isinstance(cat, str):
                tags.append(cat)

        employment_type = job_data.get("employment_type", "")
        if employment_type:
            tags.append(employment_type)

        uid = Job.generate_uid(self.source_group, raw_id=raw_id)

        return Job(
            uid=uid,
            source_group=self.source_group,
            source_name=self.source_name,
            title=title,
            company="AMD",
            location=location,
            url=job_url,
            snippet=snippet,
            posted_at=posted_at,
            raw_id=raw_id,
            tags=tags,
        )


def _strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
