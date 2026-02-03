"""Fetcher for SmartRecruiters posting API."""

import logging

from fetchers.base import BaseFetcher, resilient_get
from models import Job

logger = logging.getLogger(__name__)


class SmartRecruitersFetcher(BaseFetcher):
    source_group = "smartrecruiters"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._company_id = source_config["company_id"]

    def fetch(self) -> list[Job]:
        jobs = []
        offset = 0
        limit = 100

        while True:
            url = (
                f"https://api.smartrecruiters.com/v1/companies/{self._company_id}/postings"
                f"?offset={offset}&limit={limit}"
            )
            resp = resilient_get(url)
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("content", []):
                loc = item.get("location", {})
                location_parts = []
                if loc.get("city"):
                    location_parts.append(loc["city"])
                if loc.get("country"):
                    location_parts.append(loc["country"])
                location = ", ".join(location_parts)

                uid = Job.generate_uid(self.source_group, raw_id=item.get("id", ""))

                jobs.append(
                    Job(
                        uid=uid,
                        source_group=self.source_group,
                        source_name=self.source_name,
                        title=item.get("name", ""),
                        company=self._config.get("company", self._company_id),
                        location=location,
                        url=item.get("ref_url", item.get("company", {}).get("identifier", "")),
                        snippet="",
                        raw_id=item.get("id", ""),
                    )
                )

            total = data.get("totalFound", 0)
            offset += limit
            if offset >= total:
                break

        return jobs
