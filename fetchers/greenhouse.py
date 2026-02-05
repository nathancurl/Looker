"""Fetcher for Greenhouse job boards API."""

import logging
from datetime import datetime

from fetchers.base import BaseFetcher, resilient_get
from models import Job

logger = logging.getLogger(__name__)


class GreenhouseFetcher(BaseFetcher):
    source_group = "greenhouse"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._board_token = source_config["board_token"]

    def fetch(self) -> list[Job]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{self._board_token}/jobs?content=true"
        resp = resilient_get(url)
        resp.raise_for_status()
        data = resp.json()

        jobs = []
        for item in data.get("jobs", []):
            posted_at = None
            updated_at = item.get("updated_at")
            if updated_at:
                try:
                    posted_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

            location = ""
            loc_data = item.get("location")
            if loc_data:
                location = loc_data.get("name", "")

            # Skip description - often contains HTML entities/garbage
            snippet = ""

            uid = Job.generate_uid(self.source_group, raw_id=str(item["id"]))

            jobs.append(
                Job(
                    uid=uid,
                    source_group=self.source_group,
                    source_name=self.source_name,
                    title=item.get("title", ""),
                    company=self._config.get("company", self._board_token),
                    location=location,
                    url=item.get("absolute_url", ""),
                    snippet=snippet,
                    posted_at=posted_at,
                    raw_id=str(item["id"]),
                )
            )

        return jobs
