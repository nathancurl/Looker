"""Fetcher for Intuit Careers using Selenium (Avature/TalentBrew platform).

Intuit uses Avature ATS with TalentBrew CDN for their recruitment portal.
The careers page requires JavaScript rendering, so we use Selenium WebDriver.

URL: https://jobs.intuit.com/search-jobs
Company ID: 27595
"""

import logging
import re
import time
from datetime import datetime, timezone

from fetchers.base import BaseFetcher
from models import Job

logger = logging.getLogger(__name__)

BASE_URL = "https://jobs.intuit.com"


class IntuitFetcher(BaseFetcher):
    source_group = "intuit"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._query = source_config.get("query", "software engineer")
        self._max_pages = source_config.get("max_pages", 10)
        self._results_per_page = source_config.get("results_per_page", 15)  # Intuit shows ~15 per page
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
            logger.error("Intuit: selenium not installed")
            return []

        options = Options()
        # Use system Chromium if available (for VM compatibility)
        options.binary_location = "/usr/bin/chromium"
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
            # Force ChromeDriver v144 to match system Chromium
            service = Service(ChromeDriverManager(driver_version="144.0.7559.109").install())
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(30)

            page = 1
            while page <= self._max_pages:
                # Intuit uses page numbers (p=1, p=2, etc.)
                url = f"{BASE_URL}/search-jobs?k={self._query.replace(' ', '+')}&p={page}"

                logger.info(f"Intuit: loading page {page}...")
                driver.get(url)
                time.sleep(4)  # Wait for JavaScript to load job listings

                # Wait for job listings to load
                wait = WebDriverWait(driver, 15)
                try:
                    # Intuit uses <section class="jobs-list-section"> or similar for job cards
                    wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "article.job-item, li.jobs-list-item, a.job-link"))
                    )
                except Exception as e:
                    logger.warning(f"Intuit: no job listings found on page {page}: {e}")
                    break

                # Find all job listing elements
                # Try multiple selectors since Avature can vary
                job_elements = (
                    driver.find_elements(By.CSS_SELECTOR, "article.job-item") or
                    driver.find_elements(By.CSS_SELECTOR, "li.jobs-list-item") or
                    driver.find_elements(By.CSS_SELECTOR, "a[href*='/job/']")
                )

                logger.info(f"Intuit: found {len(job_elements)} job listings on page {page}")

                if not job_elements:
                    break

                page_jobs = []
                for job_elem in job_elements:
                    try:
                        # Extract job data from the listing
                        # Try to find the job link
                        job_link = None
                        if job_elem.tag_name == 'a':
                            job_link = job_elem
                        else:
                            job_link = job_elem.find_element(By.CSS_SELECTOR, "a[href*='/job/']")

                        href = job_link.get_attribute("href") if job_link else None
                        if not href:
                            continue

                        # Extract job ID from URL (e.g., /job/location/title/27595/12345)
                        job_id_match = re.search(r"/job/[^/]+/[^/]+/\d+/(\d+)", href)
                        if not job_id_match:
                            # Try alternative pattern
                            job_id_match = re.search(r"job[_-]?id[=/](\d+)", href, re.IGNORECASE)

                        if not job_id_match:
                            logger.debug(f"Intuit: couldn't extract job ID from {href}")
                            continue

                        job_id = job_id_match.group(1)

                        # Extract title
                        title_elem = None
                        try:
                            title_elem = (
                                job_elem.find_element(By.CSS_SELECTOR, "h2, h3, .job-title, a.job-link") if job_elem.tag_name != 'a'
                                else job_link
                            )
                            title = title_elem.text.strip() if title_elem else ""
                        except Exception:
                            title = ""

                        # Extract location
                        location = ""
                        try:
                            location_elem = job_elem.find_element(By.CSS_SELECTOR, ".job-location, .location, span[class*='location']")
                            location = location_elem.text.strip()
                        except Exception:
                            pass

                        # Generate UID
                        uid = Job.generate_uid(self.source_group, raw_id=job_id)

                        # Create Job object
                        job = Job(
                            uid=uid,
                            source_group=self.source_group,
                            source_name=self.source_name,
                            title=title or "Software Engineer",
                            company="Intuit",
                            location=location,
                            url=href,
                            snippet="",  # Snippet not easily available without clicking
                            posted_at=None,  # Date not easily available on listing page
                            raw_id=job_id,
                        )
                        page_jobs.append(job)
                        logger.debug(f"Intuit: extracted job {job_id}: {title}")

                    except Exception as e:
                        logger.warning(f"Intuit: error extracting job from element: {e}")
                        continue

                jobs.extend(page_jobs)
                logger.info(f"Intuit: extracted {len(page_jobs)} jobs from page {page}")

                # Check if there's a next page
                # Look for "Next" button or pagination indicator
                try:
                    next_button = driver.find_element(By.CSS_SELECTOR, "a.next-page, button.pagination-next, a[aria-label='Next']")
                    if not next_button.is_enabled() or 'disabled' in next_button.get_attribute("class"):
                        logger.info("Intuit: reached last page")
                        break
                except Exception:
                    # If we got fewer jobs than expected, probably last page
                    if len(page_jobs) < self._results_per_page / 2:
                        logger.info("Intuit: fewer jobs than expected, assuming last page")
                        break

                page += 1
                time.sleep(2)  # Rate limiting between pages

        except Exception as e:
            logger.error(f"Intuit: selenium fetch failed: {e}")
        finally:
            if driver:
                driver.quit()

        logger.info(f"Intuit: fetched {len(jobs)} total jobs")
        return jobs
