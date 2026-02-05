"""Fetcher for SmartRecruiters posting API."""

import logging
from datetime import datetime

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
                job_id = item.get("id", "")
                title = item.get("name", "")

                # Build job URL: https://jobs.smartrecruiters.com/{company}/{id}-{title-slug}
                title_slug = title.lower().replace(" ", "-").replace(",", "").replace("(", "").replace(")", "")
                job_url = f"https://jobs.smartrecruiters.com/{self._company_id}/{job_id}-{title_slug}"

                # Parse location
                loc = item.get("location", {})
                location_parts = []
                if loc.get("city"):
                    location_parts.append(loc["city"])
                if loc.get("region"):
                    location_parts.append(loc["region"])
                if loc.get("country"):
                    location_parts.append(loc["country"].upper())
                location = ", ".join(location_parts) if location_parts else ""

                # Check if remote
                is_remote = loc.get("remote", False)

                # Parse posted date
                posted_at = None
                released_date = item.get("releasedDate")
                if released_date:
                    try:
                        posted_at = datetime.fromisoformat(released_date.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        pass

                # Build snippet from employment type, function, and experience level
                snippet_parts = []
                emp_type = item.get("typeOfEmployment", {})
                if emp_type.get("label"):
                    snippet_parts.append(emp_type["label"])

                function = item.get("function", {})
                if function.get("label"):
                    snippet_parts.append(function["label"])

                experience = item.get("experienceLevel", {})
                if experience.get("label"):
                    snippet_parts.append(f"Level: {experience['label']}")

                snippet = " | ".join(snippet_parts)

                uid = Job.generate_uid(self.source_group, raw_id=job_id)

                jobs.append(
                    Job(
                        uid=uid,
                        source_group=self.source_group,
                        source_name=self.source_name,
                        title=title,
                        company=self._config.get("company", self._company_id),
                        location=location,
                        url=job_url,
                        snippet=snippet,
                        posted_at=posted_at,
                        remote=is_remote,
                        raw_id=job_id,
                    )
                )

            total = data.get("totalFound", 0)
            offset += limit
            if offset >= total:
                break

        return jobs
