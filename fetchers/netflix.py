"""Fetcher for Netflix Jobs via their Eightfold-powered careers portal."""

import logging
import re

from fetchers.base import BaseFetcher, resilient_get
from models import Job

logger = logging.getLogger(__name__)

# Netflix moved to Eightfold platform at explore.jobs.netflix.net
BASE_URL = "https://explore.jobs.netflix.net/api/apply/v2/jobs"


class NetflixFetcher(BaseFetcher):
    source_group = "maang"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._base_url = source_config.get("base_url", BASE_URL)

    def fetch(self) -> list[Job]:
        jobs = []
        start = 0
        num = 100  # Jobs per request

        while True:
            resp = resilient_get(
                self._base_url,
                params={"domain": "netflix.com", "start": start, "num": num},
            )
            resp.raise_for_status()
            data = resp.json()

            positions = data.get("positions", [])
            if not positions:
                break

            for item in positions:
                job_id = str(item.get("id", ""))
                title = item.get("name", "")
                location = item.get("location", "")

                # Handle multiple locations
                locations = item.get("locations", [])
                if locations and isinstance(locations, list):
                    location = locations[0] if len(locations) == 1 else " | ".join(locations[:3])

                canonical_url = item.get("canonicalPositionUrl", "")
                url = canonical_url or f"https://explore.jobs.netflix.net/careers/job/{job_id}"

                department = item.get("department", "")
                business_unit = item.get("business_unit", "")
                snippet = f"{department} - {business_unit}" if department and business_unit else department or business_unit

                raw_id = f"netflix:{job_id}"
                uid = Job.generate_uid(self.source_group, raw_id=raw_id)

                tags = [department] if department else []

                jobs.append(
                    Job(
                        uid=uid,
                        source_group=self.source_group,
                        source_name=self.source_name,
                        title=title,
                        company=self._config.get("company", "Netflix"),
                        location=location,
                        url=url,
                        snippet=snippet,
                        raw_id=raw_id,
                        tags=tags,
                    )
                )

            total = data.get("count", 0)
            start += num
            if start >= total:
                break

        return jobs


def _strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
