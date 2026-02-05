"""Fetcher for JPMorgan Chase jobs via Oracle Cloud HCM API.

JPMorgan Chase uses Oracle Fusion HCM for their recruitment portal.
The API endpoint is publicly accessible and returns job requisitions in JSON format.

API Structure:
- Base URL: https://jpmc.fa.oraclecloud.com/hcmRestApi/resources/11.13.18.05/recruitingCEJobRequisitions
- Site Number: CX_1001
- Supports keyword search, facet filtering, and pagination
- Returns detailed job metadata including location, posting dates, and descriptions

Rate Limits:
- No explicit rate limiting observed in API responses
- Standard HTTP retry logic should be sufficient
- Typical response time: 1-3 seconds for 100 results
"""

import logging
import re
from datetime import datetime
from urllib.parse import urlencode

from fetchers.base import BaseFetcher, resilient_get
from models import Job

logger = logging.getLogger(__name__)

# Oracle Cloud HCM API base URL
ORACLE_API_BASE = "https://jpmc.fa.oraclecloud.com/hcmRestApi/resources/11.13.18.05/recruitingCEJobRequisitions"
SITE_NUMBER = "CX_1001"


class JPMorganFetcher(BaseFetcher):
    """Fetcher for JPMorgan Chase jobs using Oracle Cloud HCM API."""

    source_group = "jpmorgan"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._search_keyword = source_config.get("search_keyword", "software engineer")
        self._limit = source_config.get("limit", 100)

        # Optional facet filters for categories like "Software Engineering"
        self._category_filter = source_config.get("category_filter", "")

    def fetch(self) -> list[Job]:
        """Fetch jobs from JPMorgan Chase Oracle Cloud API."""
        jobs = []
        offset = 0

        while True:
            # Build query parameters
            params = {
                "onlyData": "true",
                "expand": "requisitionList.secondaryLocations",
                "finder": f"findReqs;siteNumber={SITE_NUMBER}",
                "limit": self._limit,
                "offset": offset,
            }

            # Add keyword search if specified
            if self._search_keyword:
                params["finder"] += f",keyword={self._search_keyword}"

            # Add category filter if specified (e.g., "Software Engineering")
            if self._category_filter:
                params["finder"] += f",facetsList=CATEGORIES;CACATEGORY={self._category_filter}"

            # Make API request
            url = f"{ORACLE_API_BASE}?{urlencode(params, safe=';,')}"

            logger.debug("Fetching JPMorgan jobs: %s", url)
            resp = resilient_get(url)
            resp.raise_for_status()
            data = resp.json()

            # Extract search results - API returns search metadata wrapper
            items = data.get("items", [])
            if not items:
                break

            # The first (and only) item contains the search results
            search_result = items[0]
            requisitions = search_result.get("requisitionList", [])

            if not requisitions:
                break

            for item in requisitions:
                job_id = str(item.get("Id", ""))
                title = item.get("Title", "")
                location = item.get("PrimaryLocation", "")

                # Build job URL - Oracle Cloud uses a standard pattern
                # Example: https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/210694987
                job_url = f"https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/{SITE_NUMBER}/job/{job_id}"

                # Parse posted date
                posted_at = None
                posted_date = item.get("PostedDate")
                if posted_date:
                    try:
                        # Format is usually YYYY-MM-DD
                        posted_at = datetime.fromisoformat(posted_date)
                    except (ValueError, AttributeError, TypeError):
                        pass

                # Build snippet from available metadata
                snippet_parts = []

                job_family = item.get("JobFamily", "")
                if job_family:
                    snippet_parts.append(f"Family: {job_family}")

                job_function = item.get("JobFunction", "")
                if job_function:
                    snippet_parts.append(f"Function: {job_function}")

                short_desc = item.get("ShortDescriptionStr", "")
                if short_desc:
                    snippet_parts.append(_strip_html(short_desc))

                snippet = " | ".join(snippet_parts) if snippet_parts else ""

                # Extract tags from job metadata
                tags = []
                if job_family:
                    tags.append(job_family)
                if job_function:
                    tags.append(job_function)

                # Check for remote/location info
                location_country = item.get("PrimaryLocationCountry", "")
                if location_country:
                    tags.append(location_country)

                # Generate UID
                uid = Job.generate_uid(self.source_group, raw_id=job_id)

                jobs.append(
                    Job(
                        uid=uid,
                        source_group=self.source_group,
                        source_name=self.source_name,
                        title=title,
                        company="JPMorgan Chase",
                        location=location,
                        url=job_url,
                        snippet=snippet,
                        posted_at=posted_at,
                        raw_id=job_id,
                        tags=tags,
                    )
                )

            # Check if we've fetched all jobs
            # Total count is in the search result metadata
            total_count = search_result.get("TotalJobsCount", 0)
            offset += self._limit

            if offset >= total_count or len(requisitions) < self._limit:
                break

        logger.info("%s: fetched %d jobs", self.source_name, len(jobs))
        return jobs


def _strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
