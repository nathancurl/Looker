"""Fetcher for Jibe-powered careers sites (used by AMD, iCIMS, Rivian, etc.).

Jibe provides a JSON API at {base_url}/api/jobs with pagination support.

API Structure:
- Endpoint: {base_url}/api/jobs?page=1
- Pagination: ~10 jobs per page, empty jobs array = end
- Filtering: &categories=Engineering
- Response: {"jobs": [{"data": {...}}, ...]}

Config fields:
- base_url: e.g. "https://careers.amd.com" or "https://careers.icims.com"
- company: company name for display
- categories: optional list of category filters
- max_pages: max pages to paginate (default 200)
"""

import logging
import re
from datetime import datetime

from fetchers.base import BaseFetcher, resilient_get
from models import Job

logger = logging.getLogger(__name__)


class JibeFetcher(BaseFetcher):
    """Fetcher for Jibe/iCIMS-powered career sites with JSON API."""

    source_group = "jibe"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._base_url = source_config["base_url"].rstrip("/")
        self._api_url = f"{self._base_url}/api/jobs"
        self._careers_url = f"{self._base_url}/careers-home/jobs"
        self._company = source_config.get("company", "")
        self._categories = source_config.get("categories", [])
        self._max_pages = source_config.get("max_pages", 200)
        self._page_size = 10

    def fetch(self) -> list[Job]:
        jobs = []
        if self._categories:
            for category in self._categories:
                jobs.extend(self._fetch_category(category))
        else:
            jobs.extend(self._fetch_category(None))
        return jobs

    def _fetch_category(self, category: str | None) -> list[Job]:
        jobs = []
        page = 1

        while page <= self._max_pages:
            params: dict = {"page": page}
            if category:
                params["categories"] = category

            resp = resilient_get(
                self._api_url,
                params=params,
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

            job_list = data.get("jobs", [])
            if not job_list:
                break

            for item in job_list:
                job = self._parse_job(item)
                if job:
                    jobs.append(job)

            if len(job_list) < self._page_size:
                break

            page += 1

        return jobs

    def _parse_job(self, item: dict) -> Job | None:
        job_data = item.get("data", {})
        if not job_data:
            return None

        raw_id = str(job_data.get("req_id") or job_data.get("slug") or "")
        if not raw_id:
            return None

        title = job_data.get("title", "")
        if not title:
            return None

        city = job_data.get("city", "")
        state = job_data.get("state", "")
        country = job_data.get("country", "")
        location = ", ".join(p for p in (city, state, country) if p)

        job_url = job_data.get("apply_url", "")
        if not job_url:
            job_url = f"{self._careers_url}/{raw_id}"

        description = job_data.get("description", "") or job_data.get("qualifications", "")
        snippet = _strip_html(description)

        posted_at = None
        posted_date = job_data.get("posted_date")
        if posted_date:
            try:
                posted_at = datetime.fromisoformat(posted_date.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        uid = Job.generate_uid(self.source_group, raw_id=raw_id)

        return Job(
            uid=uid,
            source_group=self.source_group,
            source_name=self.source_name,
            title=title,
            company=self._company,
            location=location,
            url=job_url,
            snippet=snippet,
            posted_at=posted_at,
            raw_id=raw_id,
        )


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
