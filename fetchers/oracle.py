"""Fetcher for Oracle Careers (Oracle Recruiting Cloud / HCM).

Oracle uses their own Oracle Recruiting Cloud (formerly Taleo Enterprise) platform.
The API is a RESTful service hosted on Oracle Fusion Cloud infrastructure.

API Endpoint: https://eeho.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions
Site Number: CX_1 (Oracle's site identifier)

Rate Limits: Not publicly documented, but standard rate limiting applies.
Recommended: 1 request per 2-3 seconds for sustained scraping.
"""

import logging
import re
from datetime import datetime
from typing import Optional

from fetchers.base import BaseFetcher, resilient_get
from models import Job

logger = logging.getLogger(__name__)


class OracleFetcher(BaseFetcher):
    """Fetcher for Oracle Careers using Oracle Recruiting Cloud API."""

    source_group = "oracle"

    # Oracle Fusion Cloud HCM REST API base URL
    API_BASE = "https://eeho.fa.us2.oraclecloud.com/hcmRestApi/resources/latest"
    SITE_NUMBER = "CX_1"  # Oracle's career site identifier

    # Base URL for job detail pages
    CAREERS_BASE = "https://careers.oracle.com"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._keyword = source_config.get("keyword", "")
        self._location = source_config.get("location", "")
        # Oracle API always returns 25 jobs per page regardless of limit parameter
        self._limit_per_page = 25
        self._max_jobs = source_config.get("max_jobs", 500)

    def fetch(self) -> list[Job]:
        """Fetch jobs from Oracle Recruiting Cloud API.

        The API uses a finder pattern with query parameters:
        - finder: findReqs (search requisitions)
        - siteNumber: CX_1 (Oracle's site)
        - keyword: search term
        - limit/offset: pagination

        Returns nested structure: items[0].requisitionList[]
        """
        jobs = []
        offset = 0

        while len(jobs) < self._max_jobs:
            try:
                data = self._fetch_page(offset)
                if not data:
                    break

                # API returns items array with single search result object
                search_result = data.get("items", [{}])[0]
                requisitions = search_result.get("requisitionList", [])

                if not requisitions:
                    logger.info("%s: no more jobs at offset %d", self.source_name, offset)
                    break

                total_count = search_result.get("TotalJobsCount", 0)
                logger.info(
                    "%s: processing page at offset %d (total available: %d)",
                    self.source_name,
                    offset,
                    total_count,
                )

                for req in requisitions:
                    job = self._parse_job(req)
                    if job:
                        jobs.append(job)

                # Stop if we've retrieved all available jobs
                offset += len(requisitions)
                if offset >= total_count or len(jobs) >= self._max_jobs:
                    break

            except Exception:
                logger.exception("%s: failed to fetch page at offset %d", self.source_name, offset)
                break

        return jobs[: self._max_jobs]

    def _fetch_page(self, offset: int) -> Optional[dict]:
        """Fetch a single page of job requisitions."""
        url = f"{self.API_BASE}/recruitingCEJobRequisitions"

        # Build finder query string
        # Format: finder=findReqs;siteNumber=CX_1,keyword=value,offset=N,limit=25
        # Note: offset and limit MUST be in the finder string, not as separate params
        finder_parts = [f"siteNumber={self.SITE_NUMBER}"]
        if self._keyword:
            finder_parts.append(f"keyword={self._keyword}")
        if self._location:
            finder_parts.append(f"location={self._location}")

        # Add pagination parameters to finder
        finder_parts.append(f"offset={offset}")
        finder_parts.append(f"limit={self._limit_per_page}")

        finder = "findReqs;" + ",".join(finder_parts)

        params = {
            "onlyData": "true",
            "expand": "requisitionList.secondaryLocations",
            "finder": finder,
        }

        resp = resilient_get(
            url,
            params=params,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        return resp.json()

    def _parse_job(self, req: dict) -> Optional[Job]:
        """Parse a job requisition into a Job object."""
        try:
            req_id = str(req.get("Id", ""))
            if not req_id:
                return None

            title = req.get("Title", "")
            if not title:
                return None

            # Build job URL
            # Format: https://careers.oracle.com/jobs/#en/sites/jobsearch/job/[ID]
            job_url = f"{self.CAREERS_BASE}/jobs/#en/sites/jobsearch/job/{req_id}"

            # Location: primary + secondary locations
            location = req.get("PrimaryLocation", "")
            secondary_locs = req.get("secondaryLocations", [])
            if secondary_locs:
                # Add up to 2 secondary locations
                for sec_loc in secondary_locs[:2]:
                    if isinstance(sec_loc, dict):
                        loc_str = sec_loc.get("Location", "")
                        if loc_str and loc_str != location:
                            location += f", {loc_str}"
                    elif isinstance(sec_loc, str) and sec_loc != location:
                        location += f", {sec_loc}"

            # Description/snippet
            snippet = req.get("ShortDescriptionStr", "")
            if not snippet:
                # Try other description fields
                snippet = req.get("ExternalResponsibilitiesStr", "") or req.get(
                    "ExternalQualificationsStr", ""
                )
            snippet = _strip_html(snippet)

            # Posted date
            posted_at = None
            posted_date_str = req.get("PostedDate")
            if posted_date_str:
                try:
                    # Format appears to be YYYY-MM-DD
                    posted_at = datetime.strptime(posted_date_str, "%Y-%m-%d")
                except (ValueError, TypeError):
                    logger.debug("Could not parse posted date: %s", posted_date_str)

            # Tags: hot job, trending, workplace type
            tags = []
            if req.get("HotJobFlag"):
                tags.append("Hot Job")
            if req.get("TrendingFlag"):
                tags.append("Trending")
            workplace_type = req.get("WorkplaceType", "").strip()
            if workplace_type:
                tags.append(workplace_type)

            # Remote detection
            remote = False
            if location:
                location_lower = location.lower()
                remote = any(
                    keyword in location_lower
                    for keyword in ["remote", "virtual", "work from home"]
                )

            uid = Job.generate_uid(self.source_group, raw_id=req_id)

            return Job(
                uid=uid,
                source_group=self.source_group,
                source_name=self.source_name,
                title=title,
                company="Oracle",
                location=location,
                remote=remote,
                url=job_url,
                snippet=snippet,
                posted_at=posted_at,
                raw_id=req_id,
                tags=tags,
            )

        except Exception:
            logger.exception("%s: failed to parse job: %s", self.source_name, req)
            return None


def _strip_html(text: str) -> str:
    """Remove HTML tags and normalize whitespace."""
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()
