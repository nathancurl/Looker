"""Fetcher for Oracle Taleo ATS portals.

Taleo has two main deployment patterns:
1. Cloud: taleo.net hosted portals (e.g., oracle.taleo.net)
2. Legacy: Company-specific domains

This fetcher targets the Taleo REST API available on cloud deployments.
"""

import logging
import re
from datetime import datetime

from fetchers.base import BaseFetcher, resilient_get
from models import Job

logger = logging.getLogger(__name__)


class TaleoFetcher(BaseFetcher):
    source_group = "taleo"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._base_url = source_config["base_url"].rstrip("/")

    def fetch(self) -> list[Job]:
        jobs = []
        start = 0
        limit = 100

        while True:
            url = f"{self._base_url}/requisition/searchRequisitions"
            resp = resilient_get(
                url,
                params={
                    "start": start,
                    "limit": limit,
                    "sortColumn": "lastPublishedDate",
                    "sortOrder": "desc",
                },
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

            requisitions = data.get("requisitions", data.get("jobs", []))
            for item in requisitions:
                req_id = str(item.get("requisitionId", item.get("id", "")))
                title = item.get("title", item.get("jobTitle", ""))

                # Location handling varies by Taleo config
                location = item.get("location", "")
                if isinstance(location, dict):
                    city = location.get("city", "")
                    state = location.get("state", "")
                    country = location.get("country", "")
                    location = ", ".join(p for p in (city, state, country) if p)
                elif isinstance(location, list) and location:
                    location = location[0] if isinstance(location[0], str) else str(location[0])

                job_url = item.get("applyUrl", "") or f"{self._base_url}/requisition/{req_id}"

                description = item.get("description", "") or item.get("jobDescription", "")
                snippet = _strip_html(description)

                posted_at = None
                posted_date = item.get("lastPublishedDate", item.get("postedDate"))
                if posted_date:
                    try:
                        # Taleo often uses epoch milliseconds
                        if isinstance(posted_date, (int, float)):
                            posted_at = datetime.utcfromtimestamp(posted_date / 1000)
                        else:
                            posted_at = datetime.fromisoformat(str(posted_date).replace("Z", "+00:00"))
                    except (ValueError, AttributeError, TypeError):
                        pass

                category = item.get("category", "") or item.get("jobCategory", "")
                tags = [category] if category else []

                uid = Job.generate_uid(self.source_group, raw_id=req_id)

                jobs.append(
                    Job(
                        uid=uid,
                        source_group=self.source_group,
                        source_name=self.source_name,
                        title=title,
                        company=self._config.get("company", ""),
                        location=location,
                        url=job_url,
                        snippet=snippet,
                        posted_at=posted_at,
                        raw_id=req_id,
                        tags=tags,
                    )
                )

            total = data.get("total", data.get("totalCount", 0))
            start += limit
            if start >= total or not requisitions:
                break

        return jobs


def _strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
