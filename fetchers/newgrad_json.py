"""Fetcher for JSON-based new-grad repos (vanshb03, SimplifyJobs)."""

import logging
from datetime import datetime

from fetchers.base import BaseFetcher, resilient_get
from models import Job

logger = logging.getLogger(__name__)


class NewGradJSONFetcher(BaseFetcher):
    source_group = "newgrad"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._owner = source_config["owner"]
        self._repo = source_config["repo"]
        self._branch = source_config.get("branch", "dev")
        self._json_path = source_config["json_path"]

    def fetch(self) -> list[Job]:
        url = (
            f"https://raw.githubusercontent.com/{self._owner}/{self._repo}"
            f"/{self._branch}/{self._json_path}"
        )
        resp = resilient_get(url)
        resp.raise_for_status()
        listings = resp.json()

        jobs = []
        for entry in listings:
            if not entry.get("active", True) or not entry.get("is_visible", True):
                continue

            locations = entry.get("locations", [])
            location = locations[0] if locations else ""

            tags = []
            sponsorship = entry.get("sponsorship")
            if sponsorship:
                tags.append(f"sponsorship:{sponsorship}")

            posted_at = None
            date_str = entry.get("date_posted") or entry.get("date_updated")
            if date_str:
                try:
                    posted_at = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

            uid = Job.generate_uid(self.source_group, raw_id=entry.get("id"))

            jobs.append(
                Job(
                    uid=uid,
                    source_group=self.source_group,
                    source_name=self.source_name,
                    title=entry.get("title", ""),
                    company=entry.get("company_name", ""),
                    location=location,
                    url=entry.get("url", ""),
                    snippet="",
                    posted_at=posted_at,
                    raw_id=entry.get("id"),
                    tags=tags,
                )
            )

        return jobs
