"""Fetcher for Microsoft Careers API."""

import logging
import re

from fetchers.base import BaseFetcher, resilient_get
from models import Job

logger = logging.getLogger(__name__)

# Microsoft's careers API - may be intermittently unavailable
BASE_URL = "https://gcsservices.careers.microsoft.com/search/api/v1/search"


class MicrosoftFetcher(BaseFetcher):
    source_group = "maang"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._base_url = source_config.get("base_url", BASE_URL)
        self._page_size = source_config.get("page_size", 200)

    def fetch(self) -> list[Job]:
        jobs = []
        page = 1

        while True:
            try:
                resp = resilient_get(
                    self._base_url,
                    params={
                        "l": "en_us",
                        "pg": page,
                        "pgSz": self._page_size,
                        "o": "Relevance",
                        "flt": "true",
                    },
                )

                # Check for HTML error page (API down)
                content_type = resp.headers.get("content-type", "")
                if "text/html" in content_type:
                    logger.warning("Microsoft: API returned HTML instead of JSON (service may be down)")
                    return jobs

                resp.raise_for_status()
                data = resp.json()

            except Exception as e:
                logger.warning("Microsoft: API request failed on page %d: %s", page, e)
                return jobs

            result = data.get("operationResult", {}).get("result", {})
            job_list = result.get("jobs", [])

            if not job_list:
                break

            for item in job_list:
                job_id = item.get("jobId", "")
                title = item.get("title", "")
                properties = item.get("properties", {})
                locations = properties.get("primaryLocation", "")
                description = properties.get("description", "")
                snippet = _strip_html(description)
                posting_date = item.get("postingDate", "")

                url = f"https://jobs.careers.microsoft.com/global/en/job/{job_id}"

                raw_id = f"microsoft:{job_id}"
                uid = Job.generate_uid(self.source_group, raw_id=raw_id)

                jobs.append(
                    Job(
                        uid=uid,
                        source_group=self.source_group,
                        source_name=self.source_name,
                        title=title,
                        company=self._config.get("company", "Microsoft"),
                        location=locations,
                        url=url,
                        snippet=snippet,
                        raw_id=raw_id,
                    )
                )

            total_jobs = result.get("totalJobs", 0)
            if page * self._page_size >= total_jobs:
                break
            page += 1

        return jobs


def _strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
