"""Fetcher for Workday career sites using Selenium (for companies that blocked API access).

Some major companies (Verizon, Fidelity, IBM, Honeywell, Lockheed Martin,
Northrop Grumman, John Deere) return 422 errors from Workday's API.
This scraper navigates the web UI directly using Selenium.

Note: Many of these companies also block datacenter IPs from accessing the
web UI (redirecting to community.workday.com/maintenance-page). This fetcher
will detect and log that situation clearly.
"""

import logging
import os
import re
import time
from datetime import datetime, timedelta

from fetchers.base import BaseFetcher
from fetchers.proxy_utils import LocalProxyForwarder
from models import Job

logger = logging.getLogger(__name__)

# Oxylabs residential proxy credentials (for US country targeting)
_PROXY_HOST = os.environ.get("OXYLABS_PROXY_HOST", "pr.oxylabs.io")
_PROXY_PORT = int(os.environ.get("OXYLABS_PROXY_PORT", "7777"))
_PROXY_USER = os.environ.get("OXYLABS_PROXY_USER", "")
_PROXY_PASS = os.environ.get("OXYLABS_PROXY_PASS", "")


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
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from fetchers.selenium_utils import get_chrome_service
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

        use_proxy = _PROXY_USER and _PROXY_PASS
        proxy_ctx = (
            LocalProxyForwarder(_PROXY_HOST, _PROXY_PORT, _PROXY_USER, _PROXY_PASS)
            if use_proxy else None
        )

        driver = None
        jobs = []

        try:
            local_proxy_url = proxy_ctx.__enter__() if proxy_ctx else None
            if local_proxy_url:
                options.add_argument(f"--proxy-server={local_proxy_url}")
                logger.info(f"{self.source_name}: using residential proxy via {_PROXY_HOST}")

            service = get_chrome_service()
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(45)

            logger.info(f"{self.source_name}: navigating to {self._base_url}")
            driver.get(self._base_url)
            time.sleep(5)  # Wait for initial page load and JavaScript

            # Detect IP block / maintenance redirect
            current_url = driver.current_url
            title = driver.title or ""
            if "maintenance" in current_url or "community.workday.com" in current_url:
                logger.warning(
                    f"{self.source_name}: blocked by Workday (redirected to maintenance page). "
                    f"This company blocks datacenter IPs."
                )
                return []
            if title.lower() in ("error", "") and len(driver.page_source) < 2000:
                logger.warning(
                    f"{self.source_name}: Workday returned error page (likely IP block). "
                    f"Title='{title}', URL={current_url}"
                )
                return []

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

                # Wait for job title links to load (the reliable selector)
                wait = WebDriverWait(driver, 15)
                try:
                    wait.until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "a[data-automation-id='jobTitle']")
                        )
                    )
                except Exception as e:
                    logger.warning(
                        f"{self.source_name}: no job listings found on page {page + 1}"
                    )
                    break

                # Find all job title links
                title_links = driver.find_elements(
                    By.CSS_SELECTOR, "a[data-automation-id='jobTitle']"
                )
                logger.info(
                    f"{self.source_name}: found {len(title_links)} job listings on page {page + 1}"
                )

                if not title_links:
                    break

                page_jobs = []
                for title_link in title_links:
                    try:
                        title = title_link.text.strip()
                        url = title_link.get_attribute("href")
                        if not title or not url:
                            continue

                        # Navigate up to the job item container (li element)
                        try:
                            job_item = title_link.find_element(By.XPATH, "ancestor::li")
                        except:
                            job_item = None

                        # Extract location from the container
                        location = "Multiple Locations"
                        if job_item:
                            try:
                                loc_elem = job_item.find_element(
                                    By.CSS_SELECTOR, "[data-automation-id='locations'] dd"
                                )
                                location = loc_elem.text.strip() or location
                            except:
                                pass

                        # Extract posted date from the container
                        posted_at = None
                        if job_item:
                            try:
                                date_elem = job_item.find_element(
                                    By.CSS_SELECTOR, "[data-automation-id='postedOn'] dd"
                                )
                                posted_at = self._parse_workday_date(date_elem.text.strip())
                            except:
                                pass

                        uid = Job.generate_uid(self.source_group, url=url)
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

                # Try to navigate to the next page
                try:
                    next_button = None
                    for selector in [
                        "button[aria-label='next']",
                        "button[data-automation-id='paginationNext']",
                    ]:
                        try:
                            btn = driver.find_element(By.CSS_SELECTOR, selector)
                            if btn.is_displayed() and btn.is_enabled():
                                next_button = btn
                                break
                        except:
                            continue

                    if not next_button:
                        logger.info(f"{self.source_name}: no more pages to load")
                        break

                    driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                    time.sleep(1)
                    next_button.click()
                    time.sleep(3)  # Wait for new jobs to load

                except Exception as e:
                    logger.info(f"{self.source_name}: reached last page: {e}")
                    break

                page += 1
                time.sleep(2)  # Be nice to the server

        except Exception as e:
            logger.warning(f"{self.source_name}: browser error: {e}")
        finally:
            if driver:
                driver.quit()
            if proxy_ctx:
                proxy_ctx.__exit__(None, None, None)

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
