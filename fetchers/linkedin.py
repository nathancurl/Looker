"""Fetcher for LinkedIn guest jobs API.

Scrapes publicly accessible LinkedIn job search pages for specific companies.
No authentication required — uses the guest API that returns HTML fragments.

Used for 18 companies whose Workday career pages have enterprise bot protection
that blocks all automated access (Selenium, Playwright, residential proxies all fail).
"""

import logging
import random
import re
import time

from bs4 import BeautifulSoup

from fetchers.base import BaseFetcher
from models import Job

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
]

_COMMON_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

# Job ID pattern from LinkedIn URLs: /jobs/view/title-slug-1234567890
_JOB_ID_RE = re.compile(r"/jobs/view/[^?]*?(\d{8,})")


def _random_headers() -> dict:
    headers = dict(_COMMON_HEADERS)
    headers["User-Agent"] = random.choice(_UA_POOL)
    return headers


class LinkedInFetcher(BaseFetcher):
    """Fetches jobs from LinkedIn's guest API for multiple companies."""

    source_group = "linkedin"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._companies = source_config.get("companies", [])
        self._delay_range = source_config.get("request_delay", [3, 5])
        self._backoff = 0  # Current backoff seconds (0 = no backoff)
        self._max_backoff = 1800  # 30 minutes

    def fetch(self) -> list[Job]:
        import requests

        all_jobs = []
        session = requests.Session()

        for company in self._companies:
            name = company["name"]
            lid = company["linkedin_id"]

            if self._backoff > 0:
                logger.warning(
                    "LinkedIn: backing off %ds before %s", self._backoff, name
                )
                time.sleep(self._backoff)

            # Rate limit between companies
            delay = random.uniform(*self._delay_range)
            time.sleep(delay)

            try:
                jobs = self._fetch_company(session, name, lid)
                all_jobs.extend(jobs)
                # Successful request — reset backoff
                self._backoff = 0
            except _RateLimitError:
                # 429 — exponential backoff
                self._backoff = max(60, self._backoff * 2) if self._backoff else 60
                self._backoff = min(self._backoff, self._max_backoff)
                logger.warning(
                    "LinkedIn: 429 rate limited on %s, backoff now %ds",
                    name,
                    self._backoff,
                )
            except Exception as e:
                logger.warning("LinkedIn: error fetching %s: %s", name, e)

        return all_jobs

    def _fetch_company(
        self, session, company_name: str, linkedin_id: str
    ) -> list[Job]:
        """Fetch the most recent jobs for a single company."""
        import requests

        params = {
            "f_C": linkedin_id,
            "location": "United States",
            "sortBy": "DD",  # Sort by date descending
            "start": "0",
        }

        resp = session.get(
            _BASE_URL, params=params, headers=_random_headers(), timeout=15
        )

        if resp.status_code == 429:
            raise _RateLimitError()

        if resp.status_code != 200:
            logger.warning(
                "LinkedIn: %s returned %d", company_name, resp.status_code
            )
            return []

        return self._parse_jobs(resp.text, company_name)

    def _parse_jobs(self, html: str, company_name: str) -> list[Job]:
        """Parse job cards from LinkedIn HTML response."""
        soup = BeautifulSoup(html, "lxml")
        jobs = []

        for card in soup.select("li"):
            try:
                job = self._parse_card(card, company_name)
                if job:
                    jobs.append(job)
            except Exception as e:
                logger.debug("LinkedIn: error parsing card: %s", e)

        return jobs

    def _parse_card(self, card, company_name: str) -> Job | None:
        """Parse a single job card element into a Job."""
        # Extract job URL and ID
        link = card.select_one("a.base-card__full-link")
        if not link:
            return None

        url = (link.get("href") or "").strip()
        if not url:
            return None

        # Extract job ID from URL
        match = _JOB_ID_RE.search(url)
        if not match:
            return None
        job_id = match.group(1)

        # Clean URL (remove tracking params)
        url = url.split("?")[0]

        # Extract title
        title_el = card.select_one("h3.base-search-card__title")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None

        # Extract company name from card (might differ from our company_name)
        company_el = card.select_one("h4.base-search-card__subtitle")
        card_company = company_el.get_text(strip=True) if company_el else company_name

        # Extract location
        location_el = card.select_one("span.job-search-card__location")
        location = location_el.get_text(strip=True) if location_el else ""

        # Extract posted date
        posted_at = None
        time_el = card.select_one("time.job-search-card__listdate")
        if time_el:
            date_str = time_el.get("datetime", "")
            if date_str:
                try:
                    from datetime import datetime
                    posted_at = datetime.fromisoformat(date_str)
                except ValueError:
                    pass

        uid = Job.generate_uid(self.source_group, raw_id=job_id)

        return Job(
            uid=uid,
            source_group=self.source_group,
            source_name=self.source_name,
            title=title,
            company=card_company,
            location=location,
            url=url,
            snippet=f"{title} at {card_company} — {location}",
            posted_at=posted_at,
            raw_id=job_id,
        )


class _RateLimitError(Exception):
    pass
