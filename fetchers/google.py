"""Fetcher for Google Careers XML feed."""

import logging
import re
import xml.etree.ElementTree as ET

from fetchers.base import BaseFetcher, resilient_get
from models import Job

logger = logging.getLogger(__name__)

FEED_URL = "https://www.google.com/about/careers/applications/jobs/feed.xml"

# Countries to include (US, Canada, Western Europe)
ALLOWED_COUNTRIES = {
    # North America
    "US", "USA", "United States",
    "CA", "Canada",
    # Western Europe
    "UK", "United Kingdom", "GB", "Great Britain",
    "DE", "Germany",
    "FR", "France",
    "NL", "Netherlands",
    "IE", "Ireland",
    "CH", "Switzerland",
    "BE", "Belgium",
    "AT", "Austria",
    "SE", "Sweden",
    "DK", "Denmark",
    "NO", "Norway",
    "FI", "Finland",
    "ES", "Spain",
    "PT", "Portugal",
    "IT", "Italy",
    "LU", "Luxembourg",
}


class GoogleFetcher(BaseFetcher):
    source_group = "maang"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._feed_url = source_config.get("feed_url", FEED_URL)
        self._allowed_countries = source_config.get("allowed_countries", ALLOWED_COUNTRIES)

    def fetch(self) -> list[Job]:
        resp = resilient_get(self._feed_url, timeout=60)
        resp.raise_for_status()

        root = ET.fromstring(resp.content)

        jobs = []
        for item in root.iter("job"):
            # Filter by location country
            countries = _get_countries(item)
            if not _has_allowed_country(countries, self._allowed_countries):
                continue

            job_id = _text(item, "jobid")
            title = _text(item, "title")
            employer = _text(item, "employer")
            company = employer if employer else self._config.get("company", "Google")
            description = _text(item, "description")
            snippet = _strip_html(description)
            url = _text(item, "url")

            location = _build_location(item)

            raw_id = f"google:{job_id}"
            uid = Job.generate_uid(self.source_group, raw_id=raw_id)

            jobs.append(
                Job(
                    uid=uid,
                    source_group=self.source_group,
                    source_name=self.source_name,
                    title=title,
                    company=company,
                    location=location,
                    url=url,
                    snippet=snippet,
                    raw_id=raw_id,
                )
            )

        return jobs


def _text(element: ET.Element, tag: str) -> str:
    """Get text content of a child element, or empty string."""
    child = element.find(tag)
    return child.text.strip() if child is not None and child.text else ""


def _get_countries(item: ET.Element) -> list[str]:
    """Extract list of country values from item's locations."""
    countries = []
    locations_el = item.find("locations")
    if locations_el is None:
        return countries
    for loc in locations_el.findall("location"):
        country = _text(loc, "country")
        if country:
            countries.append(country)
    return countries


def _has_allowed_country(countries: list[str], allowed: set[str]) -> bool:
    """Check if any country in the list is in the allowed set."""
    if not countries:
        return False
    for country in countries:
        if country in allowed:
            return True
    return False


def _build_location(item: ET.Element) -> str:
    """Build a location string from nested <locations> structure."""
    parts = []
    locations_el = item.find("locations")
    if locations_el is None:
        return ""
    for loc in locations_el.findall("location"):
        city = _text(loc, "city")
        state = _text(loc, "state")
        country = _text(loc, "country")
        loc_parts = [p for p in (city, state, country) if p]
        if loc_parts:
            parts.append(", ".join(loc_parts))
    return " | ".join(parts)


def _strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
