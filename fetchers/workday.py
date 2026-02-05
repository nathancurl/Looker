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

        # Extract job board base URL for constructing job links
        # API URL: https://adobe.wd5.myworkdayjobs.com/wday/cxs/adobe/external_experienced/jobs
        # Job URL: https://adobe.wd5.myworkdayjobs.com/external_experienced/job/...
        parsed = urlparse(self._base_url)
        path_parts = parsed.path.split('/')
        # Path is typically: /wday/cxs/{company}/{job_board_name}/jobs
        # We want: https://{domain}/{job_board_name}
        job_board_name = path_parts[-2] if len(path_parts) >= 2 else ""
        self._job_board_base = f"{parsed.scheme}://{parsed.netloc}/{job_board_name}"

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

                # Build full URL from job board base + externalPath
                full_url = f"{self._job_board_base}{external_path}"

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
