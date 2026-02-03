"""Fetcher for Meta Careers — best-effort scraping.

Meta's careers page uses anti-scraping measures. This fetcher attempts
multiple approaches and gracefully returns [] if all fail.

The fetcher tries:
1. GraphQL API with doc_id (if configured)
2. Scraping embedded JSON data from the page

To obtain a fresh doc_id (optional, improves reliability):
1. Open https://www.metacareers.com/jobs in a browser with DevTools open
2. Filter the Network tab for "graphql" requests
3. Look for the `doc_id` parameter in the request payload
4. Update `doc_id` in config.json
"""

import json
import logging
import re

import requests

from fetchers.base import BaseFetcher, USER_AGENT, DEFAULT_TIMEOUT
from models import Job

logger = logging.getLogger(__name__)

CAREERS_URL = "https://www.metacareers.com/jobs"
GRAPHQL_URL = "https://www.metacareers.com/api/graphql/"


class MetaFetcher(BaseFetcher):
    source_group = "maang"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._doc_id = source_config.get("doc_id", "")

    def fetch(self) -> list[Job]:
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})

        # Load careers page to get tokens and possibly embedded data
        page_data = self._load_careers_page(session)
        if not page_data:
            return []

        lsd_token = page_data.get("lsd_token", "")
        embedded_jobs = page_data.get("jobs", [])

        # If we got embedded jobs from the page, use those
        if embedded_jobs:
            return self._parse_jobs(embedded_jobs)

        # Otherwise try GraphQL if we have doc_id and lsd_token
        if self._doc_id and lsd_token:
            jobs = self._fetch_via_graphql(session, lsd_token)
            if jobs:
                return jobs

        logger.warning("Meta: could not fetch jobs via any method")
        return []

    def _load_careers_page(self, session: requests.Session) -> dict:
        """Load careers page and extract tokens and any embedded job data."""
        try:
            resp = session.get(CAREERS_URL, timeout=DEFAULT_TIMEOUT)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("Meta: failed to load careers page: %s", e)
            return {}

        result = {}

        # Extract LSD token
        match = re.search(r'"LSD"\s*,\s*\[\]\s*,\s*\{"token"\s*:\s*"([^"]+)"', resp.text)
        if match:
            result["lsd_token"] = match.group(1)
        else:
            match = re.search(r'name="lsd"\s+value="([^"]+)"', resp.text)
            if match:
                result["lsd_token"] = match.group(1)

        # Try to extract embedded job data from __RELAY_DATA__ or similar
        for pattern in [
            r'__RELAY_DATA__\s*=\s*(\{.*?\});',
            r'"job_search":\s*(\{.*?"results":\s*\[.*?\].*?\})',
            r'data-content="(\{.*?job.*?\})"',
        ]:
            match = re.search(pattern, resp.text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1).replace('\\"', '"'))
                    jobs = self._extract_jobs_from_data(data)
                    if jobs:
                        result["jobs"] = jobs
                        break
                except (json.JSONDecodeError, KeyError):
                    pass

        return result

    def _extract_jobs_from_data(self, data: dict) -> list:
        """Extract job list from various possible data structures."""
        # Try common paths
        if isinstance(data, dict):
            if "job_search" in data:
                return data["job_search"].get("results", [])
            if "results" in data:
                return data["results"]
            if "data" in data and isinstance(data["data"], dict):
                return self._extract_jobs_from_data(data["data"])
        return []

    def _fetch_via_graphql(self, session: requests.Session, lsd_token: str) -> list[Job]:
        """Fetch jobs via GraphQL API."""
        jobs = []
        cursor = None

        for _ in range(50):  # Max 50 pages
            variables = json.dumps({"search_input": {"q": "", "cursor": cursor}})
            payload = {
                "doc_id": self._doc_id,
                "variables": variables,
                "lsd": lsd_token,
            }

            try:
                resp = session.post(
                    GRAPHQL_URL,
                    data=payload,
                    headers={"X-FB-LSD": lsd_token},
                    timeout=DEFAULT_TIMEOUT,
                )

                # Check for error responses
                if resp.status_code != 200:
                    logger.warning("Meta: GraphQL returned %d", resp.status_code)
                    break

                data = resp.json()
            except Exception as e:
                logger.warning("Meta: GraphQL request failed: %s", e)
                break

            # Check for GraphQL errors
            if "errors" in data:
                logger.warning("Meta: GraphQL errors: %s", data["errors"])
                break

            # Handle both possible response structures
            data_root = data.get("data", {})

            # Try job_search_with_featured_jobs.all_jobs (current format)
            results = data_root.get("job_search_with_featured_jobs", {}).get("all_jobs", [])

            # Fallback to job_search.results (legacy format)
            if not results:
                results = data_root.get("job_search", {}).get("results", [])

            if not results:
                break

            jobs.extend(self._parse_jobs(results))

            # Check for pagination
            page_info = data_root.get("job_search_with_featured_jobs", {}).get("page_info", {})
            if not page_info:
                page_info = data_root.get("job_search", {}).get("page_info", {})

            if not page_info.get("has_next_page", False):
                break
            cursor = page_info.get("end_cursor")
            if not cursor:
                break

        return jobs

    def _parse_jobs(self, items: list) -> list[Job]:
        """Parse job items into Job objects."""
        jobs = []
        for item in items:
            job_id = item.get("id", "")
            if not job_id:
                continue

            title = item.get("title", "")
            locations = item.get("locations", [])
            location = _format_locations(locations)
            url = f"https://www.metacareers.com/jobs/{job_id}"

            # Try various description fields
            description = (
                item.get("description", "") or
                item.get("short_description", "") or
                (item.get("teams", [""])[0] if item.get("teams") else "")
            )
            snippet = _strip_html(description)

            raw_id = f"meta:{job_id}"
            uid = Job.generate_uid(self.source_group, raw_id=raw_id)

            jobs.append(
                Job(
                    uid=uid,
                    source_group=self.source_group,
                    source_name=self.source_name,
                    title=title,
                    company=self._config.get("company", "Meta"),
                    location=location,
                    url=url,
                    snippet=snippet,
                    raw_id=raw_id,
                )
            )

        return jobs


def _format_locations(locations: list) -> str:
    """Format Meta location data into a readable string."""
    if not locations:
        return ""
    parts = []
    for loc in locations:
        if isinstance(loc, dict):
            city = loc.get("city", "")
            state = loc.get("state", "")
            country = loc.get("country", "")
            loc_parts = [p for p in (city, state, country) if p]
            if loc_parts:
                parts.append(", ".join(loc_parts))
        elif isinstance(loc, str):
            parts.append(loc)
    return " | ".join(parts[:3])


def _strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
