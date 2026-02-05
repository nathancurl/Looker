"""Fetcher for Rivian careers portal.

Rivian uses a Jibe/iCIMS-powered careers API that returns job listings
in JSON format. The API supports pagination and filtering by category.

API Structure:
- Base URL: https://careers.rivian.com/api/jobs
- Pagination: ?page=1 (returns 10 jobs per page, pageSize param appears ignored)
- Filtering: &categories=Software%20Engineering
- Response includes: jobs list, totalCount, filter facets
- Available categories: Software Engineering, Information Technology,
  Mechanical & Electrical Engineering, Internships, People, Quality, Sales, Service

Rate Limits:
- No explicit rate limits documented
- API returns 10 jobs per page maximum
- Fetcher uses resilient_get with exponential backoff
- Default timeout: 15 seconds
- Retry: Up to 3 attempts on connection errors

Key Features:
- Returns job data with rich metadata (location, categories, posted date)
- Supports filtering by category (e.g., "Software Engineering", "Internships")
- Provides detailed job descriptions and requirements
- Includes lat/long coordinates for locations
"""

import logging
import re
from datetime import datetime

from fetchers.base import BaseFetcher, resilient_get
from models import Job

logger = logging.getLogger(__name__)


class RivianFetcher(BaseFetcher):
    """Fetcher for Rivian careers using their Jibe/iCIMS API."""

    source_group = "rivian"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._base_url = "https://careers.rivian.com/api/jobs"
        self._categories = source_config.get("categories", [])
        # Note: API appears to return 10 jobs per page regardless of pageSize parameter
        self._page_size = 10

    def fetch(self) -> list[Job]:
        """Fetch jobs from Rivian careers API.

        Returns:
            List of Job objects matching configured filters.
        """
        jobs = []

        # If categories specified, fetch each category separately
        # Otherwise, fetch all jobs
        if self._categories:
            for category in self._categories:
                jobs.extend(self._fetch_category(category))
        else:
            jobs.extend(self._fetch_category(None))

        return jobs

    def _fetch_category(self, category: str | None) -> list[Job]:
        """Fetch jobs for a specific category or all jobs if category is None.

        Args:
            category: Category name (e.g., "Software Engineering") or None for all.

        Returns:
            List of Job objects.
        """
        jobs = []
        page = 1

        while True:
            params = {
                "page": page,
                "pageSize": self._page_size,
            }

            if category:
                params["categories"] = category
                logger.debug("Fetching Rivian jobs for category: %s (page %d)", category, page)
            else:
                logger.debug("Fetching all Rivian jobs (page %d)", page)

            resp = resilient_get(
                self._base_url,
                params=params,
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

            job_list = data.get("jobs", [])
            for item in job_list:
                job_data = item.get("data", {})

                # Extract job ID and basic info
                job_id = job_data.get("slug") or job_data.get("req_id", "")
                title = job_data.get("title", "")

                # Build location string
                city = job_data.get("city", "")
                state = job_data.get("state", "")
                country = job_data.get("country", "")
                location_parts = [p for p in (city, state, country) if p]
                location = ", ".join(location_parts)

                # Get job URL
                job_url = job_data.get("apply_url", "")
                if not job_url and job_id:
                    job_url = f"https://us-careers-rivian.icims.com/jobs/{job_id}"

                # Extract description/snippet
                description = job_data.get("description", "") or job_data.get("qualifications", "")
                snippet = _strip_html(description)

                # Parse posted date
                posted_at = None
                posted_date = job_data.get("posted_date")
                if posted_date:
                    try:
                        posted_at = datetime.fromisoformat(posted_date.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        pass

                # Extract categories/tags
                tags = []
                categories = job_data.get("categories", [])
                for cat in categories:
                    if isinstance(cat, dict) and cat.get("name"):
                        tags.append(cat["name"])
                    elif isinstance(cat, str):
                        tags.append(cat)

                # Add employment type if available
                employment_type = job_data.get("employment_type", "")
                if employment_type:
                    tags.append(employment_type)

                # Add tags2 (company/brand) if available
                tags2 = job_data.get("tags2", [])
                if tags2:
                    tags.extend(tags2)

                # Generate unique ID
                raw_id = job_id
                uid = Job.generate_uid(self.source_group, raw_id=raw_id)

                jobs.append(
                    Job(
                        uid=uid,
                        source_group=self.source_group,
                        source_name=self.source_name,
                        title=title,
                        company="Rivian",
                        location=location,
                        url=job_url,
                        snippet=snippet,
                        posted_at=posted_at,
                        raw_id=raw_id,
                        tags=tags,
                    )
                )

            # Check if we've reached the end
            # The API returns up to pageSize jobs per page
            if len(job_list) < self._page_size:
                break

            page += 1

        return jobs


def _strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace.

    Args:
        html: HTML string to clean.

    Returns:
        Plain text with collapsed whitespace.
    """
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
