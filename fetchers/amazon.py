"""Fetcher for Amazon Jobs search API."""

import logging
import re

from fetchers.base import BaseFetcher, resilient_get
from models import Job

logger = logging.getLogger(__name__)

BASE_URL = "https://www.amazon.jobs/en/search.json"


class AmazonFetcher(BaseFetcher):
    source_group = "maang"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._base_url = source_config.get("base_url", BASE_URL)
        self._result_limit = source_config.get("result_limit", 100)

    def fetch(self) -> list[Job]:
        jobs = []
        offset = 0

        while True:
            resp = resilient_get(
                self._base_url,
                params={"result_limit": self._result_limit, "offset": offset},
            )
            resp.raise_for_status()
            data = resp.json()

            hits = data.get("jobs", [])
            for item in hits:
                id_icims = item.get("id_icims", "")
                title = item.get("title", "")
                location = item.get("normalized_location", item.get("location", ""))
                job_path = item.get("job_path", "")
                url = f"https://www.amazon.jobs{job_path}" if job_path else ""

                description = item.get("description_short", "")
                snippet = _strip_html(description)

                raw_id = f"amazon:{id_icims}"
                uid = Job.generate_uid(self.source_group, raw_id=raw_id)

                jobs.append(
                    Job(
                        uid=uid,
                        source_group=self.source_group,
                        source_name=self.source_name,
                        title=title,
                        company=self._config.get("company", "Amazon"),
                        location=location,
                        url=url,
                        snippet=snippet,
                        raw_id=raw_id,
                    )
                )

            total = data.get("hits", 0)
            offset += self._result_limit
            if offset >= total or not hits:
                break

        return jobs


def _strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
