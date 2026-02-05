"""Fetcher for Yelp careers API (Jibe platform)."""

import logging
import re
from datetime import datetime

from fetchers.base import BaseFetcher, resilient_get
from models import Job

logger = logging.getLogger(__name__)


class YelpFetcher(BaseFetcher):
    """Fetcher for Yelp careers using their Jibe-powered API.

    Yelp's career site (yelp-community.career.page) uses the Jibe platform
    which provides a JSON API endpoint for job listings.

    API: https://yelp-community.career.page/api/jobs
    """

    source_group = "yelp"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        # Optional: filter by categories (e.g., ["Engineering", "Product Management"])
        self._filter_categories = source_config.get("categories", [])
        # Optional: filter by keywords in title (e.g., ["software", "engineer", "developer"])
        self._filter_keywords = source_config.get("keywords", [])

    def fetch(self) -> list[Job]:
        """Fetch jobs from Yelp's Jibe-powered API.

        Returns:
            List of Job objects matching any configured filters.
        """
        url = "https://yelp-community.career.page/api/jobs"
        resp = resilient_get(url)
        resp.raise_for_status()
        data = resp.json()

        jobs = []
        for item in data.get("jobs", []):
            job_data = item.get("data", {})

            # Apply category filter if configured
            if self._filter_categories:
                job_categories = [cat.get("name", "").strip() for cat in job_data.get("categories", [])]
                if not any(fc in job_categories for fc in self._filter_categories):
                    continue

            # Apply keyword filter if configured
            if self._filter_keywords:
                title_lower = job_data.get("title", "").lower()
                if not any(kw.lower() in title_lower for kw in self._filter_keywords):
                    continue

            # Parse posted date
            posted_at = None
            posted_date_str = job_data.get("posted_date")
            if posted_date_str:
                try:
                    # Format: "2026-02-05T00:07:00+0000"
                    posted_at = datetime.fromisoformat(posted_date_str.replace("+0000", "+00:00"))
                except (ValueError, AttributeError):
                    pass

            # Build location string
            location_parts = []
            city = job_data.get("city")
            state = job_data.get("state")
            country = job_data.get("country")

            # State might be "Remote" or actual state
            if state:
                location_parts.append(state)
            elif city:
                location_parts.append(city)

            if country and country != "United States":
                location_parts.append(country)

            location = ", ".join(location_parts) if location_parts else ""

            # Check if remote
            remote = (
                job_data.get("state", "").lower() == "remote" or
                job_data.get("location_type") == "REMOTE" or
                "remote" in job_data.get("location_name", "").lower()
            )

            # Extract snippet from description (strip HTML)
            description = job_data.get("description", "")
            snippet = self._extract_snippet(description)

            # Generate UID using req_id
            uid = Job.generate_uid(
                self.source_group,
                raw_id=job_data.get("req_id", job_data.get("slug", ""))
            )

            jobs.append(
                Job(
                    uid=uid,
                    source_group=self.source_group,
                    source_name=self.source_name,
                    title=job_data.get("title", ""),
                    company=self._config.get("company", "Yelp"),
                    location=location,
                    remote=remote,
                    url=job_data.get("apply_url", ""),
                    snippet=snippet,
                    posted_at=posted_at,
                    raw_id=job_data.get("req_id", job_data.get("slug", "")),
                )
            )

        return jobs

    @staticmethod
    def _extract_snippet(html_description: str) -> str:
        """Extract plain text snippet from HTML description.

        Args:
            html_description: HTML formatted job description

        Returns:
            Plain text snippet (first paragraph or ~200 chars)
        """
        if not html_description:
            return ""

        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', html_description)
        # Decode common HTML entities
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        # Return first ~200 chars
        if len(text) > 200:
            return text[:197] + "..."
        return text
