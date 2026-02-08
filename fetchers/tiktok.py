"""Fetcher for TikTok/ByteDance Careers using Selenium.

TikTok and ByteDance use a custom React-based careers portal (lifeattiktok.com and
joinbytedance.com) that loads job data dynamically with aggressive bot detection.
This fetcher uses Selenium with anti-detection measures to extract job postings.

Career site structure:
- TikTok main: https://careers.tiktok.com (redirects to lifeattiktok.com)
- TikTok search: https://lifeattiktok.com/search
- ByteDance main: https://jobs.bytedance.com (redirects to joinbytedance.com)
- ByteDance search: https://joinbytedance.com/search
- Job URL pattern: /search/{job_id} or /position/{job_id}

Filtering:
- Keywords can be passed to filter for relevant positions
- Recommended keywords: "new grad", "graduate", "early career", "intern", "software engineer"
- Focus on Technology team and Entry Level positions
"""

import json
import logging
import re
import time
from typing import Optional

from fetchers.base import BaseFetcher
from models import Job

logger = logging.getLogger(__name__)

TIKTOK_SEARCH_URL = "https://lifeattiktok.com/search"
BYTEDANCE_SEARCH_URL = "https://joinbytedance.com/search"
TIKTOK_BASE_URL = "https://lifeattiktok.com"
BYTEDANCE_BASE_URL = "https://joinbytedance.com"


class TikTokFetcher(BaseFetcher):
    """Fetcher for TikTok careers at lifeattiktok.com."""

    source_group = "tiktok"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._keywords = source_config.get("keywords", [])
        self._brand = source_config.get("brand", "tiktok")  # "tiktok" or "bytedance"
        self._headless = source_config.get("headless", True)
        self._max_scrolls = source_config.get("max_scrolls", 5)

        # Set URLs based on brand
        if self._brand.lower() == "bytedance":
            self._search_url = BYTEDANCE_SEARCH_URL
            self._base_url = BYTEDANCE_BASE_URL
        else:
            self._search_url = TIKTOK_SEARCH_URL
            self._base_url = TIKTOK_BASE_URL

    def fetch(self) -> list[Job]:
        """Fetch jobs from TikTok/ByteDance careers using Selenium.

        The site has aggressive bot detection, so we use Selenium with
        anti-detection measures similar to wellfound.py and ripplematch.py.
        """
        return self._fetch_with_selenium()

    def _fetch_with_selenium(self) -> list[Job]:
        """Fetch jobs using Selenium with anti-detection measures."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from webdriver_manager.chrome import ChromeDriverManager
        except ImportError:
            logger.error("%s: selenium not installed. Install with: pip install selenium webdriver-manager", self.source_name)
            return []

        # Configure Chrome with anti-detection measures
        options = Options()
        if self._headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        # Additional anti-detection measures
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        driver = None
        jobs = []

        try:
            # Use webdriver-manager to handle ChromeDriver
            # Force ChromeDriver v144 to match system Chromium
            service = Service(ChromeDriverManager(driver_version="144.0.7559.109").install())
            driver = webdriver.Chrome(service=service, options=options)

            # Additional anti-detection: override navigator.webdriver
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                """
            })

            driver.set_page_load_timeout(30)

            # Build URL with keyword filters
            url = self._search_url
            if self._keywords:
                # Use software engineer as primary filter
                params = "?keyword=software+engineer&level=0-1"  # Entry level
                url += params

            logger.info("%s: loading jobs page...", self.source_name)
            driver.get(url)

            # Wait for page to load - TikTok uses dynamic rendering
            wait = WebDriverWait(driver, 20)

            # Wait for the job listings container or job cards to appear
            time.sleep(3)  # Initial wait for JavaScript to execute

            # Try multiple scrolls to load more jobs
            last_height = driver.execute_script("return document.body.scrollHeight")
            for scroll in range(self._max_scrolls):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)  # Wait for new content to load

                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

            # Extract jobs from the DOM using Selenium
            jobs = self._extract_jobs_from_dom(driver)

            logger.info("%s: found %d jobs", self.source_name, len(jobs))

        except Exception as e:
            logger.warning("%s: Selenium fetch failed: %s", self.source_name, e)

        finally:
            if driver:
                driver.quit()

        return jobs

    def _extract_jobs_from_dom(self, driver) -> list[Job]:
        """Extract jobs directly from Selenium's DOM for better accuracy."""
        from selenium.webdriver.common.by import By

        jobs = []
        seen_ids = set()

        try:
            # Find all job links
            # TikTok uses: /position/{id}/detail or /search/{id}
            # ByteDance uses: /search/{id}
            # Both can use full URLs or relative paths
            job_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/search/'], a[href*='/position/'], a[href*='joinbytedance.com/search/'], a[href*='lifeattiktok.com']")

            logger.info("%s: found %d job links in DOM", self.source_name, len(job_links))

            for link in job_links:
                try:
                    # Extract URL
                    url = link.get_attribute("href")
                    if not url or ("/search/" not in url and "/position/" not in url):
                        continue

                    # Extract job ID from URL
                    # TikTok: /position/{id}/detail or /search/{id}
                    # ByteDance: /search/{id}
                    import re
                    job_id_match = re.search(r'/(search|position)/(\d{16,20})', url)
                    if not job_id_match:
                        logger.debug("%s: no job ID found in URL: %s", self.source_name, url)
                        continue

                    job_id = job_id_match.group(2)  # Group 2 because group 1 is 'search' or 'position'
                    if job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)

                    # Extract text content from the link element
                    # TikTok puts the job title and location in the link text
                    text = link.text.strip()

                    # Parse the text - typically format is:
                    # "Job Title\nLocation\nTeam\nEmployment Type"
                    lines = [line.strip() for line in text.split('\n') if line.strip()]

                    title = "Software Engineer Position"
                    location = "Multiple Locations"

                    if len(lines) >= 1:
                        title = lines[0]
                    if len(lines) >= 2:
                        # Second line is usually the location
                        location = lines[1]

                    # Filter by relevance
                    if title and not self._is_relevant_position(title):
                        continue

                    # Clean URL (remove query params)
                    clean_url = url.split("?")[0]

                    raw_id = job_id
                    uid = Job.generate_uid(self.source_group, raw_id=raw_id)

                    jobs.append(
                        Job(
                            uid=uid,
                            source_group=self.source_group,
                            source_name=self.source_name,
                            title=title,
                            company=self._config.get("company", "TikTok" if self._brand == "tiktok" else "ByteDance"),
                            location=location,
                            url=clean_url,
                            raw_id=raw_id,
                        )
                    )
                except Exception as e:
                    # Skip individual jobs that fail to parse
                    logger.debug("%s: failed to parse job: %s", self.source_name, e)
                    continue

        except Exception as e:
            logger.warning("%s: DOM extraction error: %s", self.source_name, e)

        return jobs

    def _parse_jobs_from_html(self, html: str) -> list[Job]:
        """Extract job listings from rendered HTML.

        TikTok's site uses Next.js with job data embedded in various formats.
        We try multiple strategies to extract job information.
        """
        jobs = []
        seen_ids = set()

        # Strategy 1: Extract from __NEXT_DATA__ JSON
        jobs.extend(self._parse_nextjs_data(html, seen_ids))

        # Strategy 2: Extract from job card patterns in HTML
        jobs.extend(self._parse_job_cards(html, seen_ids))

        # Strategy 3: Extract job IDs from URL patterns
        if not jobs:
            jobs.extend(self._parse_job_ids_from_html(html, seen_ids))

        return jobs

    def _parse_nextjs_data(self, html: str, seen_ids: set) -> list[Job]:
        """Extract job listings from Next.js embedded JSON data."""
        jobs = []

        # Try to find __NEXT_DATA__ JSON
        next_data_pattern = r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>'
        matches = re.findall(next_data_pattern, html, re.DOTALL)

        for match in matches:
            try:
                data = json.loads(match)
                # Navigate the data structure to find jobs
                jobs_data = self._extract_jobs_from_json(data)
                for job_item in jobs_data:
                    job = self._create_job_from_dict(job_item, seen_ids)
                    if job:
                        jobs.append(job)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.debug("%s: failed to parse __NEXT_DATA__: %s", self.source_name, e)
                continue

        return jobs

    def _parse_job_cards(self, html: str, seen_ids: set) -> list[Job]:
        """Parse job cards from HTML using pattern matching.

        TikTok job cards typically contain job title, location, and a link.
        """
        jobs = []

        # Pattern 1: Look for job links with /search/ or /position/ patterns
        # These often appear in href attributes
        job_link_pattern = r'href="(/(?:search|position)/(\d{19}))"'
        link_matches = re.finditer(job_link_pattern, html)

        for match in link_matches:
            job_path = match.group(1)
            job_id = match.group(2)

            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            # Try to extract job details from context around the link
            # Get text around the match (within 2000 chars before and after)
            start_pos = max(0, match.start() - 2000)
            end_pos = min(len(html), match.end() + 2000)
            context = html[start_pos:end_pos]

            title = self._extract_title_from_context(context, job_id)
            location = self._extract_location_from_context(context)

            # Filter by keywords if specified
            if self._keywords and title and not self._matches_keywords(title):
                continue

            # Only include software engineering and new grad positions
            if title and not self._is_relevant_position(title):
                continue

            url = f"{self._base_url}{job_path}"
            raw_id = job_id
            uid = Job.generate_uid(self.source_group, raw_id=raw_id)

            jobs.append(
                Job(
                    uid=uid,
                    source_group=self.source_group,
                    source_name=self.source_name,
                    title=title or f"Software Engineer Position {job_id}",
                    company=self._config.get("company", "TikTok" if self._brand == "tiktok" else "ByteDance"),
                    location=location or "Multiple Locations",
                    url=url,
                    raw_id=raw_id,
                    snippet="",
                )
            )

        return jobs

    def _extract_title_from_context(self, context: str, job_id: str) -> str:
        """Extract job title from HTML context."""
        # Look for common title patterns
        patterns = [
            # Title in h1, h2, h3 tags
            r'<h[123][^>]*>([^<]+(?:Engineer|Developer|Software|Graduate|Intern)[^<]*)</h[123]>',
            # Title in elements with "title" or "position" in class
            r'class="[^"]*(?:title|position|job-title)[^"]*"[^>]*>([^<]+)</[^>]*>',
            # Text near the job ID
            r'>' + re.escape(job_id) + r'[^<]*</[^>]+>.*?<[^>]*>([^<]+(?:Engineer|Developer|Software)[^<]*)<',
        ]

        for pattern in patterns:
            match = re.search(pattern, context, re.IGNORECASE | re.DOTALL)
            if match:
                title = match.group(1).strip()
                # Clean up HTML entities
                title = re.sub(r'&\w+;', ' ', title)
                title = re.sub(r'\s+', ' ', title).strip()
                if len(title) > 5 and len(title) < 200:
                    return title

        return ""

    def _extract_location_from_context(self, context: str) -> str:
        """Extract location from HTML context."""
        # Look for location patterns
        patterns = [
            r'location["\']?\s*[:\-]\s*["\']?([^<">]+)',
            r'<[^>]*class="[^"]*location[^"]*"[^>]*>([^<]+)</[^>]*>',
            # Common city patterns
            r'\b(San Jose|San Francisco|Seattle|New York|Austin|Los Angeles|Mountain View|Palo Alto)[^<]{0,20}(?:,\s*(?:CA|WA|NY|TX))?',
        ]

        for pattern in patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                location = match.group(1).strip()
                location = re.sub(r'\s+', ' ', location)
                if len(location) > 2 and len(location) < 100:
                    return location

        return ""

    def _is_relevant_position(self, title: str) -> bool:
        """Check if position is relevant (software engineering, new grad, etc.)."""
        title_lower = title.lower()

        # Must contain software/engineering keywords
        eng_keywords = [
            "software", "engineer", "developer", "swe", "backend", "frontend",
            "full stack", "fullstack", "machine learning", "ml", "ai", "data"
        ]
        has_eng = any(kw in title_lower for kw in eng_keywords)

        # Should be entry level / new grad
        level_keywords = [
            "new grad", "graduate", "entry", "junior", "early career",
            "university", "recent grad", "2024", "2025", "intern"
        ]
        has_level = any(kw in title_lower for kw in level_keywords)

        # Exclude certain types
        exclude_keywords = ["senior", "staff", "principal", "lead", "manager", "director"]
        is_excluded = any(kw in title_lower for kw in exclude_keywords)

        return has_eng and (has_level or not is_excluded)

    def _extract_jobs_from_json(self, data: dict, path: list = None) -> list[dict]:
        """Recursively search JSON for job listings.

        Looks for arrays of objects that contain job-like fields.
        """
        jobs = []

        if isinstance(data, dict):
            # Check if this dict looks like a job posting
            if self._looks_like_job(data):
                return [data]

            # Recurse into nested structures
            for key, value in data.items():
                if key in ("jobs", "positions", "postings", "items", "data", "results", "list"):
                    if isinstance(value, list):
                        for item in value:
                            if self._looks_like_job(item):
                                jobs.append(item)
                elif isinstance(value, (dict, list)):
                    jobs.extend(self._extract_jobs_from_json(value))

        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and self._looks_like_job(item):
                    jobs.append(item)
                elif isinstance(item, (dict, list)):
                    jobs.extend(self._extract_jobs_from_json(item))

        return jobs

    def _looks_like_job(self, data: dict) -> bool:
        """Check if a dict looks like a job posting."""
        if not isinstance(data, dict):
            return False

        # Job postings typically have these fields
        job_indicators = {
            "title", "job_title", "position_title", "position_name",
            "id", "job_id", "position_id", "post_id",
            "location", "city", "city_info",
            "description", "snippet", "requirement",
        }

        keys = set(data.keys())
        return len(keys & job_indicators) >= 2

    def _create_job_from_dict(self, job_data: dict, seen_ids: set) -> Optional[Job]:
        """Create a Job object from a job data dictionary."""
        # Extract ID
        job_id = str(
            job_data.get("id") or
            job_data.get("job_id") or
            job_data.get("position_id") or
            job_data.get("post_id") or
            ""
        )

        if not job_id or job_id in seen_ids:
            return None
        seen_ids.add(job_id)

        # Extract title
        title = (
            job_data.get("title") or
            job_data.get("job_title") or
            job_data.get("position_title") or
            job_data.get("position_name") or
            f"Software Engineer Position {job_id}"
        )

        # Filter by relevance
        if not self._is_relevant_position(title):
            return None

        # Extract location
        location = self._extract_location_from_dict(job_data)

        # Extract URL
        url = job_data.get("url") or job_data.get("job_url") or f"{self._base_url}/search/{job_id}"

        # Extract description/snippet
        snippet = (
            job_data.get("snippet") or
            job_data.get("description") or
            job_data.get("requirement") or
            ""
        )

        raw_id = job_id
        uid = Job.generate_uid(self.source_group, raw_id=raw_id)

        return Job(
            uid=uid,
            source_group=self.source_group,
            source_name=self.source_name,
            title=title,
            company=self._config.get("company", "TikTok" if self._brand == "tiktok" else "ByteDance"),
            location=location,
            url=url,
            raw_id=raw_id,
            snippet=snippet[:300] if snippet else "",
        )

    def _extract_location_from_dict(self, job_data: dict) -> str:
        """Extract location from job data dictionary."""
        location_parts = []

        # Try different location field names
        if "location" in job_data:
            loc = job_data["location"]
            if isinstance(loc, str):
                return loc
            elif isinstance(loc, dict):
                city = loc.get("city") or loc.get("city_name") or ""
                state = loc.get("state") or loc.get("state_name") or ""
                country = loc.get("country") or loc.get("country_name") or ""
                location_parts = [p for p in (city, state, country) if p]

        if not location_parts:
            city = job_data.get("city") or job_data.get("city_name") or ""
            if city:
                location_parts.append(city)
            country = job_data.get("country") or job_data.get("country_name") or ""
            if country:
                location_parts.append(country)

        return ", ".join(location_parts) if location_parts else "Multiple Locations"

    def _parse_job_ids_from_html(self, html: str, seen_ids: set) -> list[Job]:
        """Extract job listings by finding job IDs in HTML.

        TikTok/ByteDance job IDs are typically 19-digit numbers.
        Job URLs follow patterns like: /search/7531986763343300871
        """
        jobs = []

        # Pattern: /search/{19-digit-id} or /position/{19-digit-id}
        pattern = r'/(search|position)/(\d{19})'
        matches = re.findall(pattern, html)

        for endpoint, job_id in matches:
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            # Build URL
            url = f"{self._base_url}/{endpoint}/{job_id}"

            raw_id = job_id
            uid = Job.generate_uid(self.source_group, raw_id=raw_id)

            jobs.append(
                Job(
                    uid=uid,
                    source_group=self.source_group,
                    source_name=self.source_name,
                    title=f"Software Engineer Position {job_id}",
                    company=self._config.get("company", "TikTok" if self._brand == "tiktok" else "ByteDance"),
                    location="Multiple Locations",
                    url=url,
                    raw_id=raw_id,
                    snippet="",
                )
            )

        return jobs

    def _matches_keywords(self, title: str) -> bool:
        """Check if title matches any of the configured keywords."""
        title_lower = title.lower()
        return any(keyword.lower() in title_lower for keyword in self._keywords)


class ByteDanceFetcher(TikTokFetcher):
    """Fetcher for ByteDance careers at joinbytedance.com.

    This is essentially the same as TikTokFetcher but defaults to ByteDance branding.
    """

    source_group = "bytedance"

    def __init__(self, source_config: dict):
        # Force brand to bytedance
        source_config["brand"] = "bytedance"
        super().__init__(source_config)
