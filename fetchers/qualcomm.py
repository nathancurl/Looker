"""Fetcher for Qualcomm Jobs via their Eightfold-powered careers portal."""

import logging
import re

from fetchers.base import BaseFetcher, resilient_get
from models import Job

logger = logging.getLogger(__name__)

# Qualcomm uses Eightfold platform at careers.qualcomm.com
BASE_URL = "https://careers.qualcomm.com/api/apply/v2/jobs"

# Keywords that indicate entry-level/new grad positions
NEWGRAD_KEYWORDS = [
    "new grad",
    "university grad",
    "entry level",
    "entry-level",
    "junior",
    "associate",
    "early career",
    "college grad",
    "recent graduate",
]

# US states/regions to filter for
US_LOCATIONS = [
    "United States",
    "California",
    "San Diego",
    "Santa Clara",
    "Texas",
    "Austin",
    "New York",
    "Colorado",
    "Boulder",
]


class QualcommFetcher(BaseFetcher):
    source_group = "qualcomm"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._base_url = source_config.get("base_url", BASE_URL)
        self._search_query = source_config.get("search_query", "software engineer")
        self._filter_newgrad = source_config.get("filter_newgrad", True)
        self._location_filter = source_config.get("location_filter", None)

    def fetch(self) -> list[Job]:
        jobs = []
        start = 0
        num = 100  # Jobs per request

        while True:
            params = {
                "domain": "qualcomm.com",
                "start": start,
                "num": num,
            }

            # Add optional search query
            if self._search_query:
                params["query"] = self._search_query

            # Add optional location filter
            if self._location_filter:
                params["location"] = self._location_filter

            resp = resilient_get(self._base_url, params=params)
            resp.raise_for_status()
            data = resp.json()

            positions = data.get("positions", [])
            if not positions:
                break

            for item in positions:
                job_id = str(item.get("id", ""))
                title = item.get("name", "")
                location = item.get("location", "")

                # Handle multiple locations
                locations = item.get("locations", [])
                if locations and isinstance(locations, list):
                    location = (
                        locations[0]
                        if len(locations) == 1
                        else " | ".join(locations[:3])
                    )

                # Filter by new grad keywords if enabled
                if self._filter_newgrad:
                    title_lower = title.lower()
                    if not any(keyword in title_lower for keyword in NEWGRAD_KEYWORDS):
                        continue

                canonical_url = item.get("canonicalPositionUrl", "")
                url = (
                    canonical_url
                    or f"https://careers.qualcomm.com/careers/job/{job_id}"
                )

                department = item.get("department", "")
                business_unit = item.get("business_unit", "")
                work_location = item.get("work_location_option", "")

                # Build snippet with relevant info
                snippet_parts = []
                if department:
                    snippet_parts.append(department)
                if work_location:
                    snippet_parts.append(f"Work mode: {work_location}")
                if business_unit:
                    snippet_parts.append(business_unit)
                snippet = " | ".join(snippet_parts)

                raw_id = f"qualcomm:{job_id}"
                uid = Job.generate_uid(self.source_group, raw_id=raw_id)

                # Add tags
                tags = []
                if department:
                    tags.append(department)
                if work_location == "remote":
                    tags.append("remote")

                # Check if remote
                is_remote = work_location in ["remote", "hybrid"] or "remote" in title.lower()

                jobs.append(
                    Job(
                        uid=uid,
                        source_group=self.source_group,
                        source_name=self.source_name,
                        title=title,
                        company=self._config.get("company", "Qualcomm"),
                        location=location,
                        url=url,
                        snippet=snippet,
                        raw_id=raw_id,
                        tags=tags,
                        remote=is_remote,
                    )
                )

            total = data.get("count", 0)
            start += num
            if start >= total:
                break

        logger.info(
            "%s: fetched %d jobs (filtered from %d total)",
            self.source_name,
            len(jobs),
            data.get("count", 0),
        )
        return jobs


def _strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
