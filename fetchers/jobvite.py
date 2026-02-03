"""Fetcher for Jobvite ATS public job listings."""

import logging
import re
from datetime import datetime

from fetchers.base import BaseFetcher, resilient_get
from models import Job

logger = logging.getLogger(__name__)


class JobviteFetcher(BaseFetcher):
    source_group = "jobvite"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._company_id = source_config["company_id"]

    def fetch(self) -> list[Job]:
        url = f"https://jobs.jobvite.com/api/v2/{self._company_id}/jobs"
        resp = resilient_get(url)
        resp.raise_for_status()
        data = resp.json()

        jobs = []
        requisitions = data.get("requisitions", [])

        for item in requisitions:
            job_id = item.get("id", "")
            title = item.get("title", "")
            location = item.get("location", "")
            department = item.get("department", "")

            # Jobvite apply URL
            apply_url = item.get("applyUrl", "")
            if not apply_url:
                apply_url = f"https://jobs.jobvite.com/{self._company_id}/job/{job_id}"

            description = item.get("briefDescription", "") or item.get("description", "")
            snippet = _strip_html(description)

            posted_at = None
            date_posted = item.get("datePosted")
            if date_posted:
                try:
                    posted_at = datetime.fromisoformat(date_posted.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

            raw_id = f"{self._company_id}:{job_id}"
            uid = Job.generate_uid(self.source_group, raw_id=raw_id)

            tags = [department] if department else []

            jobs.append(
                Job(
                    uid=uid,
                    source_group=self.source_group,
                    source_name=self.source_name,
                    title=title,
                    company=self._config.get("company", self._company_id),
                    location=location,
                    url=apply_url,
                    snippet=snippet,
                    posted_at=posted_at,
                    raw_id=raw_id,
                    tags=tags,
                )
            )

        return jobs


def _strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
