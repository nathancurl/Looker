"""Fetcher for Lever postings API."""

import logging
from datetime import datetime, timezone

from fetchers.base import BaseFetcher, resilient_get
from models import Job

logger = logging.getLogger(__name__)


class LeverFetcher(BaseFetcher):
    source_group = "lever"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._slug = source_config["slug"]

    def fetch(self) -> list[Job]:
        url = f"https://api.lever.co/v0/postings/{self._slug}?mode=json"
        resp = resilient_get(url)
        resp.raise_for_status()
        postings = resp.json()

        if not isinstance(postings, list):
            logger.warning("Lever response is not a list for slug=%s", self._slug)
            return []

        jobs = []
        for item in postings:
            posted_at = None
            created_ms = item.get("createdAt")
            if created_ms:
                try:
                    posted_at = datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)
                except (ValueError, TypeError, OSError):
                    pass

            location = ""
            categories = item.get("categories", {})
            if categories:
                location = categories.get("location", "")

            uid = Job.generate_uid(self.source_group, raw_id=item.get("id", ""))

            jobs.append(
                Job(
                    uid=uid,
                    source_group=self.source_group,
                    source_name=self.source_name,
                    title=item.get("text", ""),
                    company=self._config.get("company", self._slug),
                    location=location,
                    url=item.get("hostedUrl", ""),
                    snippet=item.get("descriptionPlain", ""),
                    posted_at=posted_at,
                    raw_id=item.get("id", ""),
                )
            )

        return jobs
