"""Fetcher for iCIMS ATS portals."""

import logging
import re
from datetime import datetime

from fetchers.base import BaseFetcher, resilient_get
from models import Job

logger = logging.getLogger(__name__)


class ICIMSFetcher(BaseFetcher):
    source_group = "icims"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._portal_url = source_config["portal_url"].rstrip("/")

    def fetch(self) -> list[Job]:
        jobs = []
        page = 1
        page_size = 100

        while True:
            url = f"{self._portal_url}/jobs"
            resp = resilient_get(
                url,
                params={"page": page, "pageSize": page_size, "sort": "postedDate", "sortOrder": "desc"},
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

            job_list = data.get("jobs", [])
            for item in job_list:
                job_id = str(item.get("id", ""))
                title = item.get("title", "")

                # Build location from available fields
                city = item.get("city", "")
                state = item.get("state", "")
                country = item.get("country", "")
                location_parts = [p for p in (city, state, country) if p]
                location = ", ".join(location_parts)

                job_url = item.get("applyUrl", "") or f"{self._portal_url}/jobs/{job_id}"

                description = item.get("description", "") or item.get("shortDescription", "")
                snippet = _strip_html(description)

                posted_at = None
                posted_date = item.get("postedDate")
                if posted_date:
                    try:
                        posted_at = datetime.fromisoformat(posted_date.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        pass

                category = item.get("category", "") or item.get("jobCategory", "")
                tags = [category] if category else []

                raw_id = job_id
                uid = Job.generate_uid(self.source_group, raw_id=raw_id)

                jobs.append(
                    Job(
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
                )

            total_pages = data.get("totalPages", 1)
            if page >= total_pages or not job_list:
                break
            page += 1

        return jobs


def _strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
