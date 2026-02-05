"""Fetcher for Shopify Careers.

Shopify uses a custom React-based careers portal that loads job data dynamically.
There is no public API endpoint for job listings. This fetcher uses web scraping
to extract job postings from the careers page.

Limitations:
- Jobs are loaded via JavaScript, so this fetcher may miss dynamically loaded content
- No official API means the structure could change without notice
- Rate limits are enforced; this fetcher implements proper backoff and delays

Career site structure:
- Main page: https://www.shopify.com/careers
- Search page: https://www.shopify.com/careers/search
- Job URL pattern: /careers/{job-title}_{uuid}
- Early career programs: Dev Degree, Internships, APM, Design Apprentice

Filtering:
- Keywords can be passed to filter for relevant positions
- Recommended keywords: "intern", "new grad", "early career", "engineer"

Rate Limiting:
- Implements exponential backoff with jitter for 429 responses
- Adds delays between requests to avoid triggering rate limits
- Falls back to Selenium if rate limiting persists
"""

import logging
import random
import re
import time
from typing import Optional

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from fetchers.base import BaseFetcher, USER_AGENT, DEFAULT_TIMEOUT, resilient_get
from models import Job

logger = logging.getLogger(__name__)

CAREERS_URL = "https://www.shopify.com/careers"
BASE_URL = "https://www.shopify.com"

# Rate limiting configuration
DEFAULT_REQUEST_DELAY = 2.0  # Seconds between requests
MAX_RETRIES_ON_RATE_LIMIT = 3
INITIAL_BACKOFF = 5.0  # Initial backoff in seconds for rate limits


class ShopifyFetcher(BaseFetcher):
    source_group = "shopify"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._keywords = source_config.get("keywords", [])
        self._use_selenium = source_config.get("use_selenium", False)
        self._request_delay = source_config.get("request_delay", DEFAULT_REQUEST_DELAY)
        self._auto_fallback_to_selenium = source_config.get("auto_fallback_to_selenium", True)

    def fetch(self) -> list[Job]:
        """Fetch jobs from Shopify careers with proper rate limiting.

        This implementation includes:
        1. Exponential backoff with jitter for 429 rate limit responses
        2. Configurable delays between requests
        3. Automatic fallback to Selenium on persistent rate limits
        4. Support for keyword filtering (especially for new grad/early career positions)

        Rate Limiting Strategy:
        - Uses resilient HTTP requests with retry logic
        - Implements exponential backoff on rate limit errors (429)
        - Adds randomized jitter to avoid thundering herd
        - Falls back to Selenium if rate limits persist (configurable)

        Selenium Mode (use_selenium=true):
        - Handles JavaScript-rendered content
        - Scrolls page slowly to load dynamic content
        - Uses realistic browser settings to avoid detection
        - Recommended for sites with heavy rate limiting or JS rendering

        Focus on Software Engineering Positions:
        - Use keywords filter for: "engineer", "software", "new grad", "intern", "early career"
        - Jobs are parsed from URL patterns in the page HTML
        """
        if self._use_selenium:
            return self._fetch_with_selenium()
        else:
            return self._fetch_with_requests()

    def _fetch_with_requests(self) -> list[Job]:
        """Attempt to fetch jobs using requests library with rate limit handling."""
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        })

        # Try to fetch with exponential backoff on rate limits
        resp_text = None
        for attempt in range(MAX_RETRIES_ON_RATE_LIMIT):
            try:
                # Add jitter to avoid thundering herd
                if attempt > 0:
                    jitter = random.uniform(0, 1)
                    time.sleep(self._request_delay + jitter)

                logger.info("Shopify: fetching careers page (attempt %d/%d)",
                           attempt + 1, MAX_RETRIES_ON_RATE_LIMIT)

                resp = session.get(CAREERS_URL, timeout=DEFAULT_TIMEOUT)

                if resp.status_code == 429:
                    backoff = INITIAL_BACKOFF * (2 ** attempt) + random.uniform(0, 2)
                    logger.warning(
                        "Shopify: rate limited (429). Backing off for %.2f seconds (attempt %d/%d)",
                        backoff, attempt + 1, MAX_RETRIES_ON_RATE_LIMIT
                    )
                    time.sleep(backoff)
                    continue

                resp.raise_for_status()
                resp_text = resp.text
                break

            except requests.HTTPError as e:
                if e.response.status_code == 429:
                    if attempt == MAX_RETRIES_ON_RATE_LIMIT - 1:
                        logger.warning(
                            "Shopify: persistent rate limiting after %d attempts. "
                            "Consider using Selenium or increasing delays.",
                            MAX_RETRIES_ON_RATE_LIMIT
                        )
                        # Auto-fallback to Selenium if enabled
                        if self._auto_fallback_to_selenium and not self._use_selenium:
                            logger.info("Shopify: auto-falling back to Selenium due to rate limits")
                            return self._fetch_with_selenium()
                    continue
                else:
                    logger.warning("Shopify: HTTP error %d: %s", e.response.status_code, e)
                    return []
            except Exception as e:
                logger.warning("Shopify: failed to fetch careers page: %s", e)
                return []

        if not resp_text:
            logger.warning("Shopify: failed to fetch careers page after %d attempts",
                          MAX_RETRIES_ON_RATE_LIMIT)
            return []

        # Try to extract jobs from the HTML
        jobs = self._parse_jobs_from_html(resp_text)

        # Filter by keywords after fetching if specified
        if self._keywords and jobs:
            jobs = [job for job in jobs if self._matches_keywords(job.title)]

        if not jobs:
            logger.warning(
                "Shopify: no jobs found. The page may be JavaScript-rendered. "
                "Consider setting use_selenium=true in config for better results."
            )

        return jobs

    def _parse_jobs_from_html(self, html: str) -> list[Job]:
        """Extract job listings from HTML content.

        Shopify job URLs follow the pattern: /careers/{job-title}_{uuid}
        This method searches for these patterns in the HTML.
        """
        jobs = []
        seen_ids = set()

        # Pattern: /careers/{slug}_{uuid}
        # Example: /careers/usa-engineering-internships-summer-2026-usa_b2dbdf1e-ab44-46ed-9a11-69a1a1e4b20c
        pattern = r'/careers/([a-z0-9-]+)_([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})'
        matches = re.findall(pattern, html, re.IGNORECASE)

        for slug, uuid in matches:
            if uuid in seen_ids:
                continue
            seen_ids.add(uuid)

            # Convert slug to title
            title = _slug_to_title(slug)

            # Filter by keywords if specified
            if self._keywords and not self._matches_keywords(title):
                continue

            # Build URL
            url = f"{BASE_URL}/careers/{slug}_{uuid}"

            raw_id = f"shopify:{uuid}"
            uid = Job.generate_uid(self.source_group, raw_id=raw_id)

            jobs.append(
                Job(
                    uid=uid,
                    source_group=self.source_group,
                    source_name=self.source_name,
                    title=title,
                    company=self._config.get("company", "Shopify"),
                    location="Remote",  # Shopify is "Digital by Design"
                    url=url,
                    raw_id=raw_id,
                    snippet="",
                )
            )

        return jobs

    def _fetch_with_selenium(self) -> list[Job]:
        """Fetch jobs using Selenium for JavaScript rendering.

        This method requires selenium and webdriver-manager to be installed:
        pip install selenium webdriver-manager

        Implements rate limiting best practices:
        - Adds delays between page loads
        - Scrolls slowly to avoid detection
        - Uses realistic browser settings
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.support.ui import WebDriverWait
            from webdriver_manager.chrome import ChromeDriverManager
        except ImportError:
            logger.error(
                "Shopify: selenium or webdriver-manager not installed. "
                "Install with: pip install selenium webdriver-manager"
            )
            return []

        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        # Additional options to avoid detection
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        driver = None
        jobs = []

        try:
            # Use webdriver-manager to handle ChromeDriver
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.set_page_load_timeout(30)

            # Set additional properties to avoid detection
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            # Build URL with keyword filters
            url = CAREERS_URL
            if self._keywords:
                # URL encode keywords
                import urllib.parse
                keywords_param = urllib.parse.quote(" ".join(self._keywords))
                url += f"?keywords={keywords_param}"

            logger.info("Shopify: loading careers page with Selenium...")

            # Add delay before first request
            time.sleep(self._request_delay)

            driver.get(url)

            # Wait for job listings to load
            # Try multiple selectors in case page structure varies
            wait = WebDriverWait(driver, 15)
            try:
                wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/careers/']"))
                )
            except Exception:
                logger.warning("Shopify: job links not found with primary selector, trying alternatives")
                try:
                    # Try alternative selectors
                    wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-job], .job-listing, .career-item"))
                    )
                except Exception:
                    logger.warning("Shopify: no job listings found on page")

            # Scroll down slowly to load any lazy-loaded content
            logger.info("Shopify: scrolling to load dynamic content...")
            last_height = driver.execute_script("return document.body.scrollHeight")
            scroll_attempts = 0
            max_scrolls = 5

            while scroll_attempts < max_scrolls:
                # Scroll down in smaller increments for more realistic behavior
                current_position = driver.execute_script("return window.pageYOffset")
                scroll_increment = 500
                target_position = current_position + scroll_increment

                driver.execute_script(f"window.scrollTo(0, {target_position});")

                # Wait between scrolls to avoid triggering rate limits
                time.sleep(self._request_delay / 2)

                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    # Reached bottom
                    break

                last_height = new_height
                scroll_attempts += 1

            # Additional wait for any final content to load
            time.sleep(2)

            # Get page source after JavaScript execution
            html = driver.page_source
            jobs = self._parse_jobs_from_html(html)

            # Filter by keywords if specified
            if self._keywords and jobs:
                jobs = [job for job in jobs if self._matches_keywords(job.title)]

            logger.info("Shopify: found %d jobs with Selenium", len(jobs))

        except Exception as e:
            logger.error("Shopify: Selenium fetch failed: %s", e)
            return []
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

        return jobs

    def _matches_keywords(self, title: str) -> bool:
        """Check if title matches any of the configured keywords."""
        title_lower = title.lower()
        return any(keyword.lower() in title_lower for keyword in self._keywords)


def _slug_to_title(slug: str) -> str:
    """Convert URL slug to readable title."""
    # Replace hyphens with spaces and title case
    title = slug.replace("-", " ")
    title = title.title()

    # Fix common abbreviations
    replacements = {
        " Usa ": " USA ",
        " Uk ": " UK ",
        " Eu ": " EU ",
        " Api ": " API ",
        " Ui ": " UI ",
        " Ux ": " UX ",
        " Swe ": " SWE ",
        " Ml ": " ML ",
        " Ai ": " AI ",
        " Devops ": " DevOps ",
        " Ios ": " iOS ",
        " Sr ": " Sr. ",
        " Jr ": " Jr. ",
    }
    for old, new in replacements.items():
        title = title.replace(old, new)

    return title.strip()
