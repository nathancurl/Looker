"""Fetcher for Wellfound (formerly AngelList) using Selenium.

Wellfound has anti-bot protection that blocks simple HTTP requests,
so we use Selenium with a headless browser to render the JavaScript.
"""

import logging
import os
import re
import time

from fetchers.base import BaseFetcher
from models import Job

logger = logging.getLogger(__name__)

JOBS_URL = "https://wellfound.com/role/l/software-engineer"


class WellfoundFetcher(BaseFetcher):
    source_group = "wellfound"

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
            logger.error("Wellfound: selenium not installed")
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
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(30)

            logger.info("Wellfound: loading jobs page...")
            driver.get(JOBS_URL)

            # Wait for job cards to load
            wait = WebDriverWait(driver, 15)
            try:
                wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-test='JobCard']"))
                )
            except Exception:
                # Try alternative selectors
                try:
                    wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".job-card, .styles_component__"))
                    )
                except Exception:
                    logger.warning("Wellfound: no job cards found on page")
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

            # Parse job cards from the rendered HTML
            html = driver.page_source
            jobs = self._parse_jobs_from_html(html)

            logger.info("Wellfound: found %d jobs", len(jobs))

        except Exception as e:
            logger.warning("Wellfound: browser error: %s", e)

        finally:
            if driver:
                driver.quit()

        return jobs

    def _parse_jobs_from_html(self, html: str) -> list[Job]:
        """Parse job listings from Wellfound HTML."""
        jobs = []
        seen_ids = set()

        # Look for job links - format: /jobs/SLUG or /company/SLUG/jobs/ID
        job_patterns = [
            # /company/company-name/jobs/job-id
            r'href="(/company/([^/]+)/jobs/([^"/?]+))"[^>]*>.*?<[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)',
            # Direct job link with title
            r'href="(/jobs/([^"/?]+))"[^>]*>.*?([^<]+)</a>',
        ]

        for pattern in job_patterns:
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            for match in matches:
                if len(match) >= 3:
                    url_path = match[0]
                    job_id = match[2] if len(match) > 2 else match[1]
                    title = match[-1].strip() if match[-1] else ""

                    # Clean up job ID
                    job_id = re.sub(r'[^a-zA-Z0-9-]', '', job_id)

                    if not job_id or job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)

                    # Extract company from URL or title
                    company = ""
                    if "/company/" in url_path:
                        company_match = re.search(r'/company/([^/]+)/', url_path)
                        if company_match:
                            company = company_match.group(1).replace('-', ' ').title()

                    # Clean title
                    title = re.sub(r'\s+', ' ', title).strip()
                    if not title:
                        continue

                    raw_id = f"wellfound:{job_id}"
                    uid = Job.generate_uid(self.source_group, raw_id=raw_id)

                    jobs.append(
                        Job(
                            uid=uid,
                            source_group=self.source_group,
                            source_name=self.source_name,
                            title=title,
                            company=company or "Unknown",
                            url=f"https://wellfound.com{url_path}",
                            raw_id=raw_id,
                        )
                    )

        return jobs
