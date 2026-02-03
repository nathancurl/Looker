"""Fetcher for Workable widget API."""

import logging

from fetchers.base import BaseFetcher, resilient_get
from models import Job

logger = logging.getLogger(__name__)


class WorkableFetcher(BaseFetcher):
    source_group = "workable"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._subdomain = source_config["subdomain"]

    def fetch(self) -> list[Job]:
        url = f"https://apply.workable.com/api/v1/widget/accounts/{self._subdomain}"
        resp = resilient_get(url)
        resp.raise_for_status()
        data = resp.json()

        jobs = []
        for item in data.get("jobs", []):
            location_parts = []
            for key in ("city", "state", "country"):
                val = item.get(key, "")
                if val:
                    location_parts.append(val)
            location = ", ".join(location_parts)

            uid = Job.generate_uid(self.source_group, raw_id=item.get("shortcode", ""))

            jobs.append(
                Job(
                    uid=uid,
                    source_group=self.source_group,
                    source_name=self.source_name,
                    title=item.get("title", ""),
                    company=self._config.get("company", self._subdomain),
                    location=location,
                    url=item.get("url", ""),
                    snippet=item.get("shortDescription", ""),
                    raw_id=item.get("shortcode", ""),
                )
            )

        return jobs
