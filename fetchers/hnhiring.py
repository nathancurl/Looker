"""Fetcher for HN Who is Hiring via hnrss.org RSS feed."""

import logging
import re

import feedparser

from fetchers.base import BaseFetcher
from models import Job

logger = logging.getLogger(__name__)


class HNHiringFetcher(BaseFetcher):
    source_group = "hn"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._feed_url = source_config.get(
            "feed_url", "https://hnrss.org/whoishiring/jobs"
        )

    def fetch(self) -> list[Job]:
        feed = feedparser.parse(self._feed_url)

        if feed.bozo and not feed.entries:
            logger.warning("Feed parse error for %s: %s", self._feed_url, feed.bozo_exception)
            return []

        jobs = []
        for entry in feed.entries:
            link = entry.get("link", "")
            title_raw = entry.get("title", "")
            description = entry.get("description", "") or entry.get("summary", "")

            # Best-effort company parsing from first line
            company = _parse_company(title_raw, description)
            title = _parse_title(title_raw, description)

            uid = Job.generate_uid(self.source_group, url=link)

            # Strip HTML from description for snippet
            snippet = re.sub(r"<[^>]+>", " ", description)
            snippet = re.sub(r"\s+", " ", snippet).strip()

            jobs.append(
                Job(
                    uid=uid,
                    source_group=self.source_group,
                    source_name=self.source_name,
                    title=title,
                    company=company,
                    url=link,
                    snippet=snippet,
                )
            )

        return jobs


def _parse_company(title: str, description: str) -> str:
    """Best-effort company extraction from HN hiring post.

    HN hiring comments typically start with "Company Name | Location | ..."
    """
    # Try from title first
    text = title or description
    first_line = text.split("\n")[0].strip()

    # Common format: "Company | Role | Location | ..."
    if "|" in first_line:
        return first_line.split("|")[0].strip()

    # Fallback: first few words
    words = first_line.split()
    if words:
        return " ".join(words[:3])

    return "Unknown"


def _parse_title(title: str, description: str) -> str:
    """Extract job title/role from HN post."""
    text = title or description
    first_line = text.split("\n")[0].strip()

    if "|" in first_line:
        parts = [p.strip() for p in first_line.split("|")]
        if len(parts) >= 2:
            return parts[1] if parts[1] else first_line
        return first_line

    return first_line[:100] if first_line else "HN Hiring Post"
