"""Fetcher for Ripplematch using Selenium.

Ripplematch has a JavaScript-heavy interface that requires browser rendering,
so we use Selenium with a headless browser to render the page and extract jobs.
"""

import logging
import re
import time

from fetchers.base import BaseFetcher
from models import Job

logger = logging.getLogger(__name__)

JOBS_URL = "https://ripplematch.com/jobs/computer-science-majors/"


class RipplematchFetcher(BaseFetcher):
    source_group = "ripplematch"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._max_scrolls = source_config.get("max_scrolls", 10)
        self._headless = source_config.get("headless", True)

    def fetch(self) -> list[Job]:
        # Import here to make selenium optional for other fetchers
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from webdriver_manager.chrome import ChromeDriverManager
        except ImportError:
            logger.error("Ripplematch: selenium not installed")
            return []

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

        driver = None
        jobs = []

        try:
            # Use webdriver-manager to handle ChromeDriver
            service = Service(ChromeDriverManager().install())
            try:
                driver = webdriver.Chrome(service=service, options=options)
            except Exception as e:
                if "cannot find Chrome binary" in str(e):
                    logger.error(
                        "Ripplematch: Chrome/Chromium not found. "
                        "Install Chrome or set CHROME_BINARY environment variable. "
                        "On Mac: brew install --cask google-chrome"
                    )
                    return []
                raise
            driver.set_page_load_timeout(30)

            logger.info("Ripplematch: loading jobs page...")
            driver.get(JOBS_URL)

            # Wait for job listings to load
            wait = WebDriverWait(driver, 15)
            try:
                # Try multiple possible selectors for job cards
                wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "a[href*='/job/'], a[href*='ripplematch.com/v2/public/job']")
                    )
                )
            except Exception:
                logger.warning("Ripplematch: no job links found on page")
                return []

            # Scroll to load more jobs
            last_height = driver.execute_script("return document.body.scrollHeight")
            for scroll in range(self._max_scrolls):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1.5)  # Wait for content to load

                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

            # Extract jobs using Selenium's DOM parsing for better accuracy
            jobs = self._extract_jobs_from_dom(driver)

            logger.info("Ripplematch: found %d jobs", len(jobs))

        except Exception as e:
            logger.warning("Ripplematch: browser error: %s", e)

        finally:
            if driver:
                driver.quit()

        return jobs

    def _parse_jobs_from_html(self, html: str) -> list[Job]:
        """Parse job listings from Ripplematch HTML."""
        jobs = []
        seen_ids = set()

        # Extract all job titles with their positions
        title_pattern = r'<h2[^>]*class="[^"]*cardTitle[^"]*"[^>]*>([^<]+)</h2>'
        title_matches = [(m.group(1).strip(), m.start()) for m in re.finditer(title_pattern, html, re.IGNORECASE)]

        # Extract all job URLs with their positions
        url_pattern = r'href="(https://app\.ripplematch\.com/v2/public/job/([a-f0-9-]+))(?:\?[^"]*)?\"'
        url_matches = [(m.group(1), m.group(2), m.start()) for m in re.finditer(url_pattern, html, re.IGNORECASE)]

        # Match titles to URLs by proximity (assume title comes before URL in same card)
        for title, title_pos in title_matches:
            # Find the nearest URL after this title (within 5000 chars)
            matching_url = None
            matching_id = None

            for url, job_id, url_pos in url_matches:
                if url_pos > title_pos and url_pos - title_pos < 5000:
                    if job_id not in seen_ids:
                        matching_url = url
                        matching_id = job_id
                        break

            if not matching_url or not matching_id:
                continue

            seen_ids.add(matching_id)

            # Clean up HTML entities in title
            title = title.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
            title = re.sub(r'\s+', ' ', title).strip()

            # Extract company from a larger section around the title (before and after)
            section_start = max(0, title_pos - 1000)
            section_end = min(len(html), title_pos + 2000)
            section = html[section_start:section_end]
            company = self._extract_company_from_card(section)

            raw_id = f"ripplematch:{matching_id}"
            uid = Job.generate_uid(self.source_group, raw_id=raw_id)

            jobs.append(
                Job(
                    uid=uid,
                    source_group=self.source_group,
                    source_name=self.source_name,
                    title=title,
                    company=company or "Unknown",
                    url=matching_url,
                    raw_id=raw_id,
                )
            )

        return jobs

    def _extract_jobs_from_dom(self, driver) -> list[Job]:
        """Extract jobs directly from Selenium's DOM for better accuracy."""
        from selenium.webdriver.common.by import By

        jobs = []
        seen_ids = set()

        try:
            # Find all job cards
            job_cards = driver.find_elements(By.CSS_SELECTOR, "article[class*='roleCard']")

            for card in job_cards:
                try:
                    # Extract job URL
                    links = card.find_elements(By.CSS_SELECTOR, "a[href*='/v2/public/job/']")
                    if not links:
                        continue

                    url = links[0].get_attribute("href")
                    if not url:
                        continue

                    # Extract job ID from URL
                    job_id_match = re.search(r'/job/([a-f0-9-]+)', url)
                    if not job_id_match:
                        continue

                    job_id = job_id_match.group(1)
                    if job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)

                    # Extract title
                    title_elements = card.find_elements(By.CSS_SELECTOR, "h2[class*='cardTitle']")
                    title = title_elements[0].text.strip() if title_elements else "Software Engineering Position"

                    # Extract company from logo alt text
                    company = "Unknown"
                    try:
                        logo_elements = card.find_elements(By.CSS_SELECTOR, "img[alt*='logo']")
                        if logo_elements:
                            alt_text = logo_elements[0].get_attribute("alt")
                            if alt_text:
                                # Remove " logo" suffix
                                company = re.sub(r'\s+logo\s*$', '', alt_text, flags=re.IGNORECASE).strip()
                    except Exception:
                        pass

                    # Clean URL (remove query params)
                    clean_url = url.split("?")[0]

                    raw_id = job_id  # Just the ID, generate_uid will add the prefix
                    uid = Job.generate_uid(self.source_group, raw_id=raw_id)

                    jobs.append(
                        Job(
                            uid=uid,
                            source_group=self.source_group,
                            source_name=self.source_name,
                            title=title,
                            company=company,
                            url=clean_url,
                            raw_id=job_id,  # Store just the ID
                        )
                    )
                except Exception as e:
                    # Skip individual cards that fail to parse
                    continue

        except Exception as e:
            logger.warning("Ripplematch: DOM extraction error: %s", e)

        return jobs

    def _extract_title_near_url(self, html: str, url: str) -> str:
        """Extract job title from context near the URL."""
        # Escape special regex characters in URL
        escaped_url = re.escape(url)

        # Look for common patterns around job links
        patterns = [
            # Title in tag with class containing "title", "role", "position"
            rf'{escaped_url}[^>]*>([^<]+)</a>',
            # Title in nearby div/span
            rf'<[^>]*(?:title|role|position)[^>]*>([^<]+)</[^>]*>\s*.*?{escaped_url}',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                # Clean up title
                title = re.sub(r'\s+', ' ', title)
                if title and len(title) > 3:
                    return title

        return ""

    def _extract_company_from_card(self, article_html: str) -> str:
        """Extract company name from job card HTML."""
        # Company logo alt text - this is the most reliable pattern
        logo_match = re.search(r'alt="([^"]+)\s+logo"', article_html, re.IGNORECASE)
        if logo_match:
            company = logo_match.group(1).strip()
            # Clean up HTML entities
            company = company.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
            company = re.sub(r'\s+', ' ', company)
            if company and len(company) > 1:
                return company

        # Fallback patterns if logo not found
        patterns = [
            # Company in element with company-related class
            r'<[^>]*class="[^"]*company[^"]*"[^>]*>([^<]+)</[^>]*>',
            # Company in specific divs or spans
            r'<(?:div|span)[^>]*>([A-Z][A-Za-z0-9\s&.,]+(?:Inc\.|LLC|Corp\.|Company|Technologies)?)</(?:div|span)>',
        ]

        for pattern in patterns:
            match = re.search(pattern, article_html, re.IGNORECASE)
            if match:
                company = match.group(1).strip()
                company = re.sub(r'\s+', ' ', company)
                company = company.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                if company and len(company) > 1 and len(company) < 100:
                    return company

        return ""
