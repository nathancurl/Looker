"""Fetcher for Goldman Sachs Careers (higher.gs.com).

Goldman Sachs uses the "Higher" platform powered by Next.js with client-side
Apollo GraphQL for job data. The site uses Contentful CMS for content management.

API Discovery Method:
This implementation uses browser DevTools inspection to discover the GraphQL API.
The actual endpoint and query structure must be determined by:

1. Open https://higher.gs.com/results in Chrome with DevTools (Network tab)
2. Filter for "graphql" or "Fetch/XHR" requests
3. Apply filters (e.g., "Engineering" division) and observe the network requests
4. Look for POST requests to GraphQL endpoints
5. Copy the endpoint URL, headers, query, and variables

Known Architecture:
- Platform: Higher (custom careers platform by Goldman Sachs)
- Technology: Next.js + Apollo GraphQL + Contentful CMS
- Frontend: Client-side data fetching (empty initialApolloState)
- Build ID: dab3d37481e81fb56a6c41211f838bc273f2fe41 (as of Feb 2026)

Implementation Notes:
- GraphQL endpoint needs to be discovered (not publicly documented)
- May require specific headers or authentication tokens
- Contentful CMS is used but specific space/access tokens are not exposed
- Rate limiting strategy: conservative delays between requests
"""

import json
import logging
import re
import time
from typing import Optional

import requests

from fetchers.base import BaseFetcher, USER_AGENT, DEFAULT_TIMEOUT, resilient_post
from models import Job

logger = logging.getLogger(__name__)

# Base URLs
CAREERS_URL = "https://higher.gs.com/results"
BASE_URL = "https://higher.gs.com"

# GraphQL endpoint (discovered via browser DevTools network inspection)
GRAPHQL_ENDPOINT = "https://api-higher.gs.com/gateway/api/v1/graphql"

# Actual GraphQL query structure (discovered from network requests)
DEFAULT_GRAPHQL_QUERY = """
query GetRoles($searchQueryInput: RoleSearchQueryInput!) {
  roleSearch(searchQueryInput: $searchQueryInput) {
    totalCount
    items {
      roleId
      corporateTitle
      jobTitle
      jobFunction
      locations {
        primary
        state
        country
        city
        __typename
      }
      status
      division
      skills
      jobType {
        code
        description
        __typename
      }
      externalSource {
        sourceId
        __typename
      }
      __typename
    }
    __typename
  }
}
"""

# Filter parameters for new grad/early career engineering roles
# Based on the actual API structure
DEFAULT_EXPERIENCES = ["EARLY_CAREER", "PROFESSIONAL"]
DEFAULT_DIVISIONS = ["Engineering"]
DEFAULT_EXPERIENCE_LEVELS = ["Analyst", "Summer Analyst", "New Analyst"]


class GoldmanSachsFetcher(BaseFetcher):
    """Fetcher for Goldman Sachs jobs from higher.gs.com.

    This fetcher attempts multiple strategies to retrieve job data:
    1. GraphQL API (if endpoint and query are properly configured)
    2. URL pattern scraping from the careers page
    3. Embedded JSON data extraction from Next.js page

    Configuration Options:
    - graphql_endpoint: Custom GraphQL endpoint URL
    - graphql_query: Custom GraphQL query string
    - filters: Job filter criteria (divisions, levels, regions)
    - use_graphql: Enable/disable GraphQL fetching (default: True)
    - keywords: Keywords to filter job titles (e.g., ["Software Engineer", "Developer"])
    """

    source_group = "goldmansachs"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._graphql_endpoint = source_config.get("graphql_endpoint", GRAPHQL_ENDPOINT)
        self._query = source_config.get("graphql_query", DEFAULT_GRAPHQL_QUERY)
        self._use_graphql = source_config.get("use_graphql", True)
        self._keywords = source_config.get("keywords", [])
        self._request_delay = source_config.get("request_delay", 1.0)

        # API filter parameters
        self._experiences = source_config.get("experiences", DEFAULT_EXPERIENCES)
        self._divisions = source_config.get("divisions", DEFAULT_DIVISIONS)
        self._experience_levels = source_config.get("experience_levels", DEFAULT_EXPERIENCE_LEVELS)
        self._search_term = source_config.get("search_term", "")
        self._page_size = source_config.get("page_size", 100)  # Max results per page

    def fetch(self) -> list[Job]:
        """Fetch jobs from Goldman Sachs careers site.

        Attempts multiple strategies in order:
        1. GraphQL API (if enabled and configured)
        2. URL pattern scraping from careers page
        3. Embedded Next.js data extraction

        Returns:
            List of Job objects
        """
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "application/json, text/html",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.goldmansachs.com/",
        })

        jobs = []

        # Strategy 1: Try GraphQL API if enabled
        if self._use_graphql and self._query:
            logger.info("GoldmanSachs: attempting GraphQL API fetch...")
            jobs = self._fetch_via_graphql(session)
            if jobs:
                logger.info("GoldmanSachs: successfully fetched %d jobs via GraphQL", len(jobs))
                return jobs
            else:
                logger.info("GoldmanSachs: GraphQL fetch returned no jobs, trying fallback methods")

        # Strategy 2: Try to scrape URLs from the careers page
        logger.info("GoldmanSachs: attempting URL pattern scraping...")
        jobs = self._fetch_via_url_scraping(session)
        if jobs:
            logger.info("GoldmanSachs: successfully fetched %d jobs via URL scraping", len(jobs))
            return jobs

        # Strategy 3: Try to parse embedded data from the page
        logger.info("GoldmanSachs: attempting embedded data extraction...")
        jobs = self._fetch_via_page_scraping(session)
        if jobs:
            logger.info("GoldmanSachs: successfully fetched %d jobs via embedded data", len(jobs))
            return jobs

        logger.warning(
            "GoldmanSachs: All fetch strategies failed. This fetcher requires "
            "GraphQL endpoint discovery via browser DevTools for best results. "
            "See module docstring for instructions."
        )
        return []

    def _fetch_via_graphql(self, session: requests.Session) -> list[Job]:
        """Fetch jobs via GraphQL API.

        This method requires:
        - Valid graphql_endpoint in config
        - Valid graphql_query in config
        - May require authentication tokens/headers (to be discovered)

        The GraphQL endpoint and query structure need to be discovered via
        browser DevTools by inspecting network requests on higher.gs.com.
        """
        try:
            # Build GraphQL request payload
            variables = self._build_query_variables()
            payload = {
                "query": self._query,
                "variables": variables,
            }

            # Add delay to avoid rate limiting
            time.sleep(self._request_delay)

            # Use resilient_post for automatic retries
            resp = resilient_post(
                self._graphql_endpoint,
                json=payload,
                timeout=DEFAULT_TIMEOUT,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
            )

            if resp.status_code == 404:
                logger.debug("GoldmanSachs: GraphQL endpoint not found (404). Endpoint may need to be discovered.")
                return []

            if resp.status_code != 200:
                logger.warning("GoldmanSachs: GraphQL returned %d: %s", resp.status_code, resp.text[:200])
                return []

            data = resp.json()

            # Check for GraphQL errors
            if "errors" in data:
                logger.warning("GoldmanSachs: GraphQL errors: %s", data["errors"])
                return []

            # Extract jobs from response (structure depends on actual API)
            jobs_data = self._extract_jobs_from_graphql(data)
            return self._parse_jobs(jobs_data)

        except requests.exceptions.RequestException as e:
            logger.debug("GoldmanSachs: GraphQL request failed: %s", e)
            return []
        except Exception as e:
            logger.warning("GoldmanSachs: Unexpected error in GraphQL fetch: %s", e, exc_info=True)
            return []

    def _fetch_via_url_scraping(self, session: requests.Session) -> list[Job]:
        """Fetch jobs by scraping job URLs from the careers page.

        This method extracts job posting URLs from the HTML and creates
        Job objects from the URL patterns and any visible metadata.

        Goldman Sachs job URLs follow the pattern:
        https://higher.gs.com/roles/{job_id}
        """
        try:
            # Build URL with filter query params
            params = self._build_url_params()

            time.sleep(self._request_delay)

            resp = session.get(CAREERS_URL, params=params, timeout=30)
            resp.raise_for_status()

            # Extract job URLs from the page
            jobs = self._extract_jobs_from_urls(resp.text)

            # Filter by keywords if specified
            if self._keywords and jobs:
                jobs = [job for job in jobs if self._matches_keywords(job.title)]

            return jobs

        except requests.exceptions.RequestException as e:
            logger.debug("GoldmanSachs: URL scraping failed: %s", e)
            return []
        except Exception as e:
            logger.warning("GoldmanSachs: Unexpected error in URL scraping: %s", e)
            return []

    def _extract_jobs_from_urls(self, html: str) -> list[Job]:
        """Extract job data from URLs found in the HTML.

        Looks for patterns like:
        - /roles/{job_id}
        - /roles/{job_id}/{slug}
        """
        jobs = []
        seen_ids = set()

        # Pattern: /roles/{numeric_id} or /roles/{numeric_id}/{slug}
        pattern = r'/roles/(\d+)(?:/([a-z0-9-]+))?'
        matches = re.findall(pattern, html, re.IGNORECASE)

        for job_id, slug in matches:
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            # Convert slug to title if available
            if slug:
                title = _slug_to_title(slug)
            else:
                title = f"Goldman Sachs Position {job_id}"

            # Build URL
            url = f"{BASE_URL}/roles/{job_id}"
            if slug:
                url = f"{BASE_URL}/roles/{job_id}/{slug}"

            raw_id = f"goldmansachs:{job_id}"
            uid = Job.generate_uid(self.source_group, raw_id=raw_id)

            jobs.append(
                Job(
                    uid=uid,
                    source_group=self.source_group,
                    source_name=self.source_name,
                    title=title,
                    company=self._config.get("company", "Goldman Sachs"),
                    location="Multiple Locations",  # Will be updated if we get more data
                    url=url,
                    raw_id=raw_id,
                    snippet="",
                )
            )

        return jobs

    def _fetch_via_page_scraping(self, session: requests.Session) -> list[Job]:
        """Attempt to extract job data from the careers page.

        The Higher platform may embed initial job data in the page HTML
        within __NEXT_DATA__ or other script tags.
        """
        try:
            # Build URL with filter query params
            params = self._build_url_params()
            resp = session.get(CAREERS_URL, params=params, timeout=30)
            resp.raise_for_status()

            # Try to extract embedded job data
            jobs_data = self._extract_embedded_jobs(resp.text)
            if jobs_data:
                return self._parse_jobs(jobs_data)

        except Exception as e:
            logger.warning("GoldmanSachs: Page scraping failed: %s", e)

        return []

    def _build_query_variables(self, page_number: int = 0) -> dict:
        """Build GraphQL query variables based on actual API structure.

        Based on the discovered API, the searchQueryInput takes:
        - page: {pageSize, pageNumber}
        - sort: {sortStrategy, sortOrder}
        - filters: array (structure TBD - using empty array for now)
        - experiences: ["EARLY_CAREER", "PROFESSIONAL"]
        - searchTerm: string for keyword search

        Note: The exact filter structure needs more investigation.
        For now, we use searchTerm for filtering and rely on client-side filtering.
        """
        # Build search term from divisions and keywords
        search_terms = []

        if self._search_term:
            search_terms.append(self._search_term)

        # Add divisions to search if specified
        if self._divisions:
            search_terms.extend(self._divisions)

        # Combine search terms
        combined_search = " ".join(search_terms)

        # For now, use empty filters array
        # The API filter structure requires more investigation
        filters = []

        return {
            "searchQueryInput": {
                "page": {
                    "pageSize": self._page_size,
                    "pageNumber": page_number
                },
                "sort": {
                    "sortStrategy": "RELEVANCE",
                    "sortOrder": "DESC"
                },
                "filters": filters,
                "experiences": self._experiences,
                "searchTerm": combined_search.strip()
            }
        }

    def _build_url_params(self) -> dict:
        """Build URL query parameters for page scraping fallback.

        The Higher platform may use query parameters for filters,
        though most data is loaded via client-side GraphQL.
        """
        params = {}

        # Add divisions if specified
        if self._divisions:
            params["division"] = ",".join(self._divisions)

        # Add experience levels
        if self._experience_levels:
            params["experience_level"] = ",".join(self._experience_levels)

        # Add search term
        if self._search_term:
            params["q"] = self._search_term

        return params

    def _extract_jobs_from_graphql(self, data: dict) -> list[dict]:
        """Extract job list from GraphQL response.

        Based on actual API structure discovered:
        {
          "data": {
            "roleSearch": {
              "totalCount": 123,
              "items": [
                {
                  "roleId": "12345",
                  "corporateTitle": "...",
                  "jobTitle": "...",
                  "jobFunction": "...",
                  "locations": {...},
                  "division": "...",
                  "skills": [...],
                  ...
                }
              ]
            }
          }
        }
        """
        if not isinstance(data, dict):
            return []

        # Navigate to data.roleSearch.items
        if "data" not in data:
            return []

        data = data["data"]
        if "roleSearch" not in data:
            return []

        role_search = data["roleSearch"]
        if not isinstance(role_search, dict):
            return []

        items = role_search.get("items", [])
        total_count = role_search.get("totalCount", 0)

        logger.debug("GoldmanSachs: GraphQL returned %d total jobs, %d in current page",
                    total_count, len(items))

        return items if isinstance(items, list) else []

    def _extract_embedded_jobs(self, html: str) -> list[dict]:
        """Extract job data from embedded JSON in page HTML."""
        # Try __NEXT_DATA__ script tag
        match = re.search(
            r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            html,
            re.DOTALL
        )
        if match:
            try:
                next_data = json.loads(match.group(1))
                # Try to find jobs in the Next.js data structure
                jobs = self._find_jobs_in_nextdata(next_data)
                if jobs:
                    return jobs
            except json.JSONDecodeError as e:
                logger.debug("GoldmanSachs: Failed to parse __NEXT_DATA__: %s", e)

        # Try other embedded data patterns
        for pattern in [
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
            r'window\.__APOLLO_STATE__\s*=\s*({.*?});',
        ]:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    jobs = self._find_jobs_in_data(data)
                    if jobs:
                        return jobs
                except json.JSONDecodeError:
                    continue

        return []

    def _find_jobs_in_nextdata(self, data: dict) -> list[dict]:
        """Find job listings in Next.js data structure."""
        if not isinstance(data, dict):
            return []

        # Check pageProps.initialApolloState
        page_props = data.get("props", {}).get("pageProps", {})
        apollo_state = page_props.get("initialApolloState", {})

        if apollo_state:
            return self._find_jobs_in_data(apollo_state)

        return []

    def _find_jobs_in_data(self, data: dict, max_depth: int = 5) -> list[dict]:
        """Recursively search for job arrays in data structure."""
        if max_depth <= 0 or not isinstance(data, dict):
            return []

        # Look for arrays that might be job listings
        for key, value in data.items():
            if isinstance(value, list) and value:
                # Check if this looks like a jobs array
                if self._looks_like_jobs_array(value):
                    return value
            elif isinstance(value, dict):
                # Recurse into nested objects
                jobs = self._find_jobs_in_data(value, max_depth - 1)
                if jobs:
                    return jobs

        return []

    def _looks_like_jobs_array(self, arr: list) -> bool:
        """Check if an array looks like it contains job objects."""
        if not arr or not isinstance(arr[0], dict):
            return False

        first = arr[0]
        # Check for common job field names
        job_indicators = {"title", "id", "location", "role", "position", "jobTitle"}
        return bool(job_indicators & set(first.keys()))

    def _parse_jobs(self, items: list) -> list[Job]:
        """Parse job items from GraphQL response into Job objects.

        Based on actual API response structure:
        {
          "roleId": "123456",
          "corporateTitle": "Associate",
          "jobTitle": "Software Engineer - New Grad",
          "jobFunction": "Technology",
          "locations": {
            "primary": "New York",
            "state": "New York",
            "country": "United States",
            "city": "New York"
          },
          "division": "Engineering",
          "skills": ["Java", "Python"],
          "jobType": {"code": "...", "description": "..."},
          "status": "ACTIVE"
        }
        """
        jobs = []

        for item in items:
            if not isinstance(item, dict):
                continue

            # Extract job ID (roleId field in actual API)
            job_id = str(item.get("roleId", ""))

            if not job_id:
                # Skip jobs without ID
                logger.debug("GoldmanSachs: Skipping job without roleId")
                continue

            # Extract title (use jobTitle, fallback to corporateTitle)
            title = item.get("jobTitle") or item.get("corporateTitle") or f"Role {job_id}"

            # Filter by keywords if specified
            if self._keywords and not self._matches_keywords(title):
                continue

            # Extract location from locations object
            locations_data = item.get("locations", {})
            location = self._format_location(locations_data)

            # Build job URL
            url = f"{BASE_URL}/roles/{job_id}"

            # Build snippet from available fields
            snippet_parts = []

            division = item.get("division")
            if division:
                snippet_parts.append(f"Division: {division}")

            job_function = item.get("jobFunction")
            if job_function:
                snippet_parts.append(f"Function: {job_function}")

            corporate_title = item.get("corporateTitle")
            if corporate_title:
                snippet_parts.append(f"Level: {corporate_title}")

            skills = item.get("skills", [])
            if skills and isinstance(skills, list):
                skills_str = ", ".join(skills[:5])  # Limit to 5 skills
                snippet_parts.append(f"Skills: {skills_str}")

            snippet = " | ".join(snippet_parts)

            # Check for remote work
            remote = self._is_remote(item)

            # Generate UID
            raw_id = f"goldmansachs:{job_id}"
            uid = Job.generate_uid(self.source_group, raw_id=raw_id)

            # Build tags from metadata
            tags = []
            if division:
                tags.append(division)
            if job_function:
                tags.append(job_function)
            if corporate_title:
                tags.append(corporate_title)

            jobs.append(
                Job(
                    uid=uid,
                    source_group=self.source_group,
                    source_name=self.source_name,
                    title=title,
                    company=self._config.get("company", "Goldman Sachs"),
                    location=location,
                    remote=remote,
                    url=url,
                    snippet=snippet,
                    raw_id=raw_id,
                    tags=tags,
                )
            )

        return jobs

    def _format_location(self, location_data) -> str:
        """Format location data into a readable string.

        Actual API structure for locations is an array:
        [
          {
            "primary": true,
            "city": "New York",
            "state": "New York",
            "country": "United States"
          }
        ]
        """
        if isinstance(location_data, str):
            return location_data

        if isinstance(location_data, list):
            # Handle array of locations (actual API structure)
            locations = []
            for loc in location_data:
                if isinstance(loc, str):
                    locations.append(loc)
                elif isinstance(loc, dict):
                    # Build location string from city, state, country
                    parts = []
                    city = loc.get("city")
                    state = loc.get("state")
                    country = loc.get("country")

                    if city:
                        parts.append(city)
                    # Only add state if it's different from city (avoid "New York, New York")
                    if state and state != city:
                        # Skip state if it's already in the city string
                        if not (city and state in city):
                            parts.append(state)
                    if country:
                        parts.append(country)

                    if parts:
                        locations.append(", ".join(parts))

            # Prioritize primary location if multiple locations exist
            if len(locations) > 1:
                # Find primary location
                for i, loc in enumerate(location_data):
                    if isinstance(loc, dict) and loc.get("primary"):
                        # Move primary to front
                        primary_str = locations[i]
                        return primary_str + (f" +{len(locations)-1} more" if len(locations) > 1 else "")

            return " | ".join(locations[:3])  # Limit to 3 locations

        if isinstance(location_data, dict):
            # Single location object (fallback)
            parts = []
            city = location_data.get("city")
            state = location_data.get("state")
            country = location_data.get("country")

            if city:
                parts.append(city)
            if state and state != city:
                parts.append(state)
            if country:
                parts.append(country)

            return ", ".join(parts) if parts else ""

        return ""

    def _is_remote(self, item: dict) -> bool:
        """Determine if a job is remote.

        Check locations object and job type for remote indicators.
        """
        # Check job type
        job_type = item.get("jobType", {})
        if isinstance(job_type, dict):
            description = job_type.get("description", "").lower()
            if "remote" in description or "virtual" in description:
                return True

        # Check locations
        locations = item.get("locations", {})
        if isinstance(locations, dict):
            for key, value in locations.items():
                if isinstance(value, str):
                    value_lower = value.lower()
                    if "remote" in value_lower or "virtual" in value_lower:
                        return True

        # Check title
        title = item.get("jobTitle", "").lower()
        if "remote" in title:
            return True

        return False

    def _matches_keywords(self, title: str) -> bool:
        """Check if title matches any of the configured keywords."""
        if not self._keywords:
            return True
        title_lower = title.lower()
        return any(keyword.lower() in title_lower for keyword in self._keywords)

    def _clean_text(self, text: str) -> str:
        """Clean HTML and extra whitespace from text."""
        if not text:
            return ""

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", " ", text)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text)
        # Truncate to reasonable length
        text = text.strip()
        if len(text) > 300:
            text = text[:297] + "..."

        return text


def _slug_to_title(slug: str) -> str:
    """Convert URL slug to readable title.

    Args:
        slug: URL-friendly slug (e.g., "software-engineer-new-grad")

    Returns:
        Human-readable title (e.g., "Software Engineer New Grad")
    """
    if not slug:
        return ""

    # Replace hyphens and underscores with spaces
    title = slug.replace("-", " ").replace("_", " ")

    # Title case
    title = title.title()

    # Fix common abbreviations and acronyms
    replacements = {
        " Usa ": " USA ",
        " Uk ": " UK ",
        " Nyc ": " NYC ",
        " Sf ": " SF ",
        " La ": " LA ",
        " Api ": " API ",
        " Ui ": " UI ",
        " Ux ": " UX ",
        " Gs ": " GS ",
        " It ": " IT ",
        " Ai ": " AI ",
        " Ml ": " ML ",
        " Swe ": " SWE ",
        " Qa ": " QA ",
        " Devops ": " DevOps ",
        " Ios ": " iOS ",
        " Macos ": " macOS ",
        " Aws ": " AWS ",
        " Gcp ": " GCP ",
        " Sql ": " SQL ",
        " Jr ": " Jr. ",
        " Sr ": " Sr. ",
        " Vp ": " VP ",
    }

    for old, new in replacements.items():
        title = title.replace(old, new)

    return title.strip()
