"""Fetcher for Workday internal JSON API."""

import logging
from datetime import datetime
from urllib.parse import urlparse

from fetchers.base import BaseFetcher, resilient_post
from models import Job

logger = logging.getLogger(__name__)

DEFAULT_PAYLOAD = {
    "appliedFacets": {},
    "limit": 20,
    "offset": 0,
    "searchText": "",
}


class WorkdayFetcher(BaseFetcher):
    source_group = "workday"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._base_url = source_config["base_url"]
        self._payload_template = source_config.get("payload", dict(DEFAULT_PAYLOAD))

    def fetch(self) -> list[Job]:
        jobs = []
        offset = 0
        limit = self._payload_template.get("limit", 20)

        while True:
            payload = dict(self._payload_template)
            payload["offset"] = offset

            resp = resilient_post(
                self._base_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

            job_postings = data.get("jobPostings", [])
            for item in job_postings:
                title = item.get("title", "")
                location = item.get("locationsText", "")
                external_path = item.get("externalPath", "")

                # Build full URL from base_url domain + externalPath
                parsed = urlparse(self._base_url)
                full_url = f"{parsed.scheme}://{parsed.netloc}{external_path}"

                bullet_fields = item.get("bulletFields", [])
                snippet = " | ".join(bullet_fields) if bullet_fields else ""

                posted_at = None
                posted_on = item.get("postedOn")
                if posted_on:
                    try:
                        posted_at = datetime.fromisoformat(posted_on.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        pass

                uid = Job.generate_uid(self.source_group, url=full_url)

                jobs.append(
                    Job(
                        uid=uid,
                        source_group=self.source_group,
                        source_name=self.source_name,
                        title=title,
                        company=self._config.get("company", ""),
                        location=location,
                        url=full_url,
                        snippet=snippet,
                        posted_at=posted_at,
                    )
                )

            total = data.get("total", 0)
            offset += limit
            if offset >= total or not job_postings:
                break

        return jobs
