"""Fetcher for Ashby public posting API (REST)."""

import logging
from datetime import datetime

from fetchers.base import BaseFetcher, resilient_get
from models import Job

logger = logging.getLogger(__name__)


class AshbyFetcher(BaseFetcher):
    source_group = "ashby"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        # Allow config to override source_group
        if "source_group" in source_config:
            self.source_group = source_config["source_group"]
        self._clientname = source_config["clientname"]

    def fetch(self) -> list[Job]:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{self._clientname}"
        resp = resilient_get(url)
        resp.raise_for_status()
        data = resp.json()

        jobs = []
        for item in data.get("jobs", []):
            posted_at = None
            published = item.get("publishedAt")
            if published:
                try:
                    posted_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

            uid = Job.generate_uid(self.source_group, raw_id=item.get("id", ""))

            jobs.append(
                Job(
                    uid=uid,
                    source_group=self.source_group,
                    source_name=self.source_name,
                    title=item.get("title", ""),
                    company=self._config.get("company", self._clientname),
                    location=item.get("location", ""),
                    url=item.get("jobUrl", ""),
                    snippet=item.get("descriptionPlain", ""),
                    posted_at=posted_at,
                    raw_id=item.get("id", ""),
                )
            )

        return jobs
