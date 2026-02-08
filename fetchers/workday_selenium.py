"""Fetcher for Workday career sites using Selenium (for companies that blocked API access).

Some major companies (Visa, Verizon, Fidelity, IBM, Honeywell, Lockheed Martin,
Northrop Grumman, John Deere) now return 401/422 errors from Workday's API.
This scraper navigates the web UI directly using Selenium.
"""

import logging
import re
import time
from datetime import datetime, timedelta

from fetchers.base import BaseFetcher
from models import Job

logger = logging.getLogger(__name__)


class WorkdaySeleniumFetcher(BaseFetcher):
    source_group = "workday"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._base_url = source_config["base_url"]
        self._max_pages = source_config.get("max_pages", 10)
        self._headless = source_config.get("headless", True)
        self._company = source_config.get("company", "")

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
            logger.error(f"{self.source_name}: selenium not installed")
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

            logger.info(f"{self.source_name}: navigating to {self._base_url}")
            driver.get(self._base_url)
            time.sleep(5)  # Wait for initial page load and JavaScript

            # Try to accept cookies if modal appears
            try:
                cookie_button = driver.find_element(
                    By.CSS_SELECTOR,
                    "button[data-automation-id='legalNoticeAcceptButton']"
                )
                cookie_button.click()
                time.sleep(1)
            except:
                pass  # No cookie modal or already dismissed

            page = 0
            total_scraped = 0

            while page < self._max_pages:
                logger.info(f"{self.source_name}: scraping page {page + 1}")

                # Wait for job listings to load
                wait = WebDriverWait(driver, 15)
                try:
                    wait.until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "li[data-automation-id='listItem']")
                        )
                    )
                except Exception as e:
                    logger.warning(
                        f"{self.source_name}: no job listings found on page {page + 1}: {e}"
                    )
                    break

                # Find all job listing items
                job_elements = driver.find_elements(
                    By.CSS_SELECTOR, "li[data-automation-id='listItem']"
                )
                logger.info(
                    f"{self.source_name}: found {len(job_elements)} job listings on page {page + 1}"
                )

                if not job_elements:
                    break

                page_jobs = []
                for job_elem in job_elements:
                    try:
                        # Extract title
                        title = ""
                        try:
                            title_elem = job_elem.find_element(
                                By.CSS_SELECTOR, "a[data-automation-id='jobTitle']"
                            )
                            title = title_elem.text.strip()
                        except:
                            # Fallback: try to find any link with job title
                            try:
                                title_elem = job_elem.find_element(By.CSS_SELECTOR, "a")
                                title = title_elem.text.strip().split('\n')[0]
                            except:
                                logger.warning(f"{self.source_name}: could not extract title")
                                continue

                        # Extract URL
                        url = ""
                        try:
                            link_elem = job_elem.find_element(
                                By.CSS_SELECTOR, "a[data-automation-id='jobTitle']"
                            )
                            url = link_elem.get_attribute("href")
                        except:
                            # Fallback: get first link
                            try:
                                link_elem = job_elem.find_element(By.CSS_SELECTOR, "a")
                                url = link_elem.get_attribute("href")
                            except:
                                logger.warning(f"{self.source_name}: could not extract URL")
                                continue

                        # Extract location
                        location = "Multiple Locations"
                        try:
                            # Try multiple possible location selectors
                            location_selectors = [
                                "dd[data-automation-id='location']",
                                "div[data-automation-id='location']",
                                "span[data-automation-id='location']",
                            ]
                            for selector in location_selectors:
                                try:
                                    location_elem = job_elem.find_element(By.CSS_SELECTOR, selector)
                                    location = location_elem.text.strip()
                                    if location:
                                        break
                                except:
                                    continue
                        except:
                            pass

                        # Extract posted date (optional)
                        posted_at = None
                        try:
                            date_selectors = [
                                "dd[data-automation-id='postedOn']",
                                "time[data-automation-id='postedOn']",
                            ]
                            for selector in date_selectors:
                                try:
                                    date_elem = job_elem.find_element(By.CSS_SELECTOR, selector)
                                    date_text = date_elem.text.strip()
                                    posted_at = self._parse_workday_date(date_text)
                                    if posted_at:
                                        break
                                except:
                                    continue
                        except:
                            pass

                        # Generate UID from URL
                        uid = Job.generate_uid(self.source_group, url=url)

                        # Create snippet
                        snippet = f"{title} at {self._company} - {location}"

                        page_jobs.append(
                            Job(
                                uid=uid,
                                source_group=self.source_group,
                                source_name=self.source_name,
                                title=title,
                                company=self._company,
                                location=location,
                                url=url,
                                snippet=snippet,
                                posted_at=posted_at,
                            )
                        )
                    except Exception as e:
                        logger.warning(f"{self.source_name}: error parsing job listing: {e}")
                        continue

                jobs.extend(page_jobs)
                total_scraped += len(page_jobs)
                logger.info(
                    f"{self.source_name}: extracted {len(page_jobs)} jobs from page {page + 1}"
                )

                # Try to click "Load More" or "Next" button
                try:
                    # Look for various pagination button patterns
                    pagination_selectors = [
                        "button[data-automation-id='showMoreJobs']",
                        "button[aria-label='next']",
                        "button.css-1hwfws3",  # Common Workday pagination button class
                    ]

                    clicked = False
                    for selector in pagination_selectors:
                        try:
                            next_button = driver.find_element(By.CSS_SELECTOR, selector)
                            if next_button.is_displayed() and next_button.is_enabled():
                                driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                                time.sleep(1)
                                next_button.click()
                                time.sleep(3)  # Wait for new jobs to load
                                clicked = True
                                break
                        except:
                            continue

                    if not clicked:
                        logger.info(f"{self.source_name}: no more pages to load")
                        break

                except Exception as e:
                    logger.info(f"{self.source_name}: reached last page or pagination failed: {e}")
                    break

                page += 1
                time.sleep(2)  # Be nice to the server

        except Exception as e:
            logger.warning(f"{self.source_name}: browser error: {e}")
        finally:
            if driver:
                driver.quit()

        logger.info(f"{self.source_name}: fetched {len(jobs)} total jobs")
        return jobs

    def _parse_workday_date(self, date_text: str) -> datetime | None:
        """Parse Workday date strings like 'Posted 2 days ago' or 'Posted Today'."""
        if not date_text:
            return None

        try:
            date_text = date_text.lower().strip()
            now = datetime.now()

            # Handle "Posted Today" or "Today"
            if "today" in date_text:
                return now

            # Handle "Posted Yesterday" or "Yesterday"
            if "yesterday" in date_text:
                return now - timedelta(days=1)

            # Handle "Posted X days ago" or "X days ago"
            days_match = re.search(r'(\d+)\s*days?\s*ago', date_text)
            if days_match:
                days = int(days_match.group(1))
                return now - timedelta(days=days)

            # Handle "Posted X hours ago" or "X hours ago"
            hours_match = re.search(r'(\d+)\s*hours?\s*ago', date_text)
            if hours_match:
                hours = int(hours_match.group(1))
                return now - timedelta(hours=hours)

            # Handle "Posted 30+ days ago"
            if "30+" in date_text or "30 +" in date_text:
                return now - timedelta(days=30)

            # Try to parse as absolute date (e.g., "01/15/2026")
            for fmt in ["%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y"]:
                try:
                    return datetime.strptime(date_text.split()[0], fmt)
                except:
                    continue

        except Exception as e:
            logger.debug(f"{self.source_name}: could not parse date '{date_text}': {e}")

        return None
