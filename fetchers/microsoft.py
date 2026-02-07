"""Fetcher for Microsoft Careers using Selenium (Eightfold AI platform).

Microsoft migrated from gcsservices API to Eightfold AI platform at
apply.careers.microsoft.com in early 2026.
"""

import logging
import re
import time

from fetchers.base import BaseFetcher
from models import Job

logger = logging.getLogger(__name__)

BASE_URL = "https://apply.careers.microsoft.com/careers"


class MicrosoftFetcher(BaseFetcher):
    source_group = "maang"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._query = source_config.get("query", "software engineer")
        self._max_pages = source_config.get("max_pages", 10)
        self._results_per_page = source_config.get("results_per_page", 100)
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
            logger.error("Microsoft: selenium not installed")
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

            page = 0
            while page < self._max_pages:
                start_offset = page * self._results_per_page
                url = f"{BASE_URL}?query={self._query.replace(' ', '+')}&start={start_offset}&sort_by=relevance"

                logger.info(f"Microsoft: loading page {page + 1} (offset {start_offset})...")
                driver.get(url)
                time.sleep(3)  # Wait for JavaScript to load

                # Wait for job cards to load
                wait = WebDriverWait(driver, 15)
                try:
                    wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "a[href^='/careers/job/']"))
                    )
                except Exception as e:
                    logger.warning(f"Microsoft: no job cards found on page {page + 1}: {e}")
                    break

                # Find all job card links
                job_elements = driver.find_elements(By.CSS_SELECTOR, "a[href^='/careers/job/']")
                logger.info(f"Microsoft: found {len(job_elements)} job cards on page {page + 1}")

                if not job_elements:
                    break

                page_jobs = []
                for job_elem in job_elements:
                    try:
                        # Extract job data from the card
                        href = job_elem.get_attribute("href")
                        job_id_match = re.search(r"/careers/job/(\d+)", href)
                        if not job_id_match:
                            continue

                        job_id = job_id_match.group(1)

                        # Find title within the card
                        try:
                            title_elem = job_elem.find_element(By.CSS_SELECTOR, ".title-1aNJK")
                            title = title_elem.text.strip()
                        except:
                            # Fallback: parse from full text
                            try:
                                full_text = job_elem.text.strip()
                                lines = [l.strip() for l in full_text.split('\n') if l.strip()]
                                title = lines[0] if lines else "Microsoft Position"
                            except:
                                title = "Microsoft Position"

                        # Find location
                        try:
                            location_elem = job_elem.find_element(By.CSS_SELECTOR, ".fieldValue-3kEar")
                            location = location_elem.text.strip()
                        except:
                            # Fallback: parse from full text (location is usually second line)
                            try:
                                full_text = job_elem.text.strip()
                                lines = [l.strip() for l in full_text.split('\n') if l.strip()]
                                location = lines[1] if len(lines) > 1 else "Multiple Locations"
                            except:
                                location = "Multiple Locations"

                        # Build full URL
                        if href.startswith("/"):
                            url = f"https://apply.careers.microsoft.com{href}"
                        else:
                            url = href

                        raw_id = f"microsoft:{job_id}"
                        uid = Job.generate_uid(self.source_group, raw_id=raw_id)

                        # Create snippet from title (no description available in list view)
                        snippet = f"{title} at Microsoft - {location}"

                        page_jobs.append(
                            Job(
                                uid=uid,
                                source_group=self.source_group,
                                source_name=self.source_name,
                                title=title,
                                company="Microsoft",
                                location=location,
                                url=url,
                                snippet=snippet,
                                raw_id=raw_id,
                            )
                        )
                    except Exception as e:
                        logger.warning(f"Microsoft: error parsing job card: {e}")
                        continue

                jobs.extend(page_jobs)
                logger.info(f"Microsoft: extracted {len(page_jobs)} jobs from page {page + 1}")

                # Check if we got fewer results than expected (last page)
                if len(job_elements) < self._results_per_page:
                    logger.info("Microsoft: reached last page")
                    break

                page += 1
                time.sleep(2)  # Be nice to the server

        except Exception as e:
            logger.warning(f"Microsoft: browser error: {e}")
        finally:
            if driver:
                driver.quit()

        logger.info(f"Microsoft: fetched {len(jobs)} total jobs")
        return jobs
