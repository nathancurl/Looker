"""Fetcher for Tesla Jobs using Selenium.

Tesla uses Oracle Taleo Business Edition (TBE) and implements aggressive
anti-bot protection (Akamai) that blocks most automated requests.

This fetcher uses Selenium with headless Chrome and anti-detection measures
to navigate the Tesla careers page and extract software engineering job postings,
focusing on new grad/early career positions.

NOTE: Akamai bot protection is extremely sophisticated and may still block
automated requests. For best results:
1. Use headless=False to allow manual CAPTCHA solving if needed
2. Consider running from a residential IP address
3. Add delays between requests
4. Rotate user agents and browser fingerprints
5. Consider using a service like BrightData or ScrapingBee for production

The fetcher is structured to work when bot protection is bypassed, and follows
the same pattern as wellfound.py and ripplematch.py for consistency.
"""

import logging
import re
import time
from typing import Optional

from fetchers.base import BaseFetcher
from models import Job

logger = logging.getLogger(__name__)

# Tesla careers URLs to try
TESLA_CAREERS_URLS = [
    "https://www.tesla.com/careers/search/",
    "https://www.tesla.com/careers/search/?country=US&type=3",
    "https://www.tesla.com/careers/search/?query=software%20engineer",
]

# Taleo API endpoint (alternative approach)
TALEO_SEARCH_URL = "https://cho.tbe.taleo.net/cho01/ats/careers/v2/searchJobs"


class TeslaFetcher(BaseFetcher):
    """Fetcher for Tesla jobs using Selenium.

    Uses headless Chrome with anti-detection measures to bypass Akamai
    bot protection and extract software engineering job postings.
    """

    source_group = "tesla"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._headless = source_config.get("headless", True)
        self._max_scrolls = source_config.get("max_scrolls", 10)
        self._filter_keywords = source_config.get("filter_keywords", [
            "software",
            "engineer",
            "developer",
            "programming",
            "new grad",
            "university",
            "recent graduate",
            "entry level",
            "early career"
        ])

    def fetch(self) -> list[Job]:
        """Fetch Tesla jobs using Selenium with anti-detection measures."""
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
            logger.error("Tesla: selenium not installed")
            return []

        options = Options()
        if self._headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--start-maximized")

        # Realistic user agent
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # Anti-detection measures
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        # Additional privacy/fingerprinting measures
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--lang=en-US")

        # Set preferences to appear more like a real browser
        prefs = {
            "profile.default_content_setting_values.notifications": 2,
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False
        }
        options.add_experimental_option("prefs", prefs)

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
                        "Tesla: Chrome/Chromium not found. "
                        "Install Chrome or set CHROME_BINARY environment variable. "
                        "On Mac: brew install --cask google-chrome"
                    )
                    return []
                raise

            driver.set_page_load_timeout(30)

            # Add comprehensive stealth JavaScript to mask automation
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en']
                    });
                    window.chrome = {
                        runtime: {}
                    };
                    Object.defineProperty(navigator, 'permissions', {
                        get: () => ({
                            query: () => Promise.resolve({state: 'prompt'})
                        })
                    });
                """
            })

            # Try different URLs - first visit Tesla homepage to establish session
            logger.info("Tesla: visiting homepage first to establish session...")
            driver.get("https://www.tesla.com/")
            import random
            time.sleep(random.uniform(2, 4))  # Random delay

            # Now navigate to careers
            url_to_use = self._config.get("url", TESLA_CAREERS_URLS[0])
            logger.info(f"Tesla: loading careers page: {url_to_use}")
            driver.get(url_to_use)

            # Wait for job cards to load
            wait = WebDriverWait(driver, 20)
            try:
                # Wait for job results to appear - try multiple selectors
                selectors_to_wait = [
                    "article",
                    ".job-card",
                    "[class*='result']",
                    "tbody tr",
                    "[class*='posting']",
                    "a[href*='/careers/']",
                ]

                loaded = False
                for selector in selectors_to_wait:
                    try:
                        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                        logger.info(f"Tesla: found elements with selector: {selector}")
                        loaded = True
                        break
                    except Exception:
                        continue

                if not loaded:
                    logger.warning("Tesla: no job cards found with any selector")

                time.sleep(3)  # Additional wait for JavaScript to render
            except Exception as e:
                logger.warning(f"Tesla: wait exception: {e}")

            # Scroll to load more jobs
            last_height = driver.execute_script("return document.body.scrollHeight")
            for scroll in range(self._max_scrolls):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)  # Wait for content to load

                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

            # Debug: Save page source for inspection
            page_source = driver.page_source
            logger.info(f"Tesla: page source size: {len(page_source)} bytes")

            if self._config.get("save_html", False):
                import os
                debug_path = "/tmp/tesla_careers_debug.html"
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(page_source)
                logger.info(f"Tesla: saved page source to {debug_path}")

            # Check for Akamai block
            if self._is_akamai_blocked(page_source):
                logger.error(
                    "Tesla: Request blocked by Akamai bot protection. "
                    "Try running with headless=False or using a different IP/proxy."
                )
                return []

            if len(page_source) < 10000:
                logger.warning(f"Tesla: page source is suspiciously small ({len(page_source)} bytes), might be blocked")

            # Extract jobs from DOM
            jobs = self._extract_jobs_from_dom(driver)

            # Filter for software engineering / new grad positions
            jobs = [job for job in jobs if self._matches_filters(job)]

            logger.info("Tesla: found %d matching jobs", len(jobs))

        except Exception as e:
            logger.warning("Tesla: browser error: %s", e)

        finally:
            if driver:
                driver.quit()

        return jobs

    def _extract_jobs_from_dom(self, driver) -> list[Job]:
        """Extract jobs directly from Selenium's DOM."""
        from selenium.webdriver.common.by import By

        jobs = []
        seen_ids = set()

        try:
            # Find all job cards/articles
            # Tesla's job board may use various selectors
            job_elements = []

            # Try multiple possible selectors
            for selector in [
                "tbody tr",  # Taleo often uses table rows
                "article",
                "[class*='job']",
                "[class*='result']",
                "[data-job-id]",
                "li[class*='posting']",
                ".job-card",
                "tr[class*='row']",
            ]:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and len(elements) > job_elements.__len__():
                        job_elements = elements
                        logger.info(f"Tesla: found {len(elements)} elements with selector '{selector}'")
                except Exception:
                    continue

            if not job_elements:
                # Fallback: parse from page source
                logger.info("Tesla: no job elements found via selectors, parsing HTML...")
                return self._parse_jobs_from_html(driver.page_source)

            logger.info(f"Tesla: processing {len(job_elements)} job elements...")

            for element in job_elements:
                try:
                    # Extract job URL
                    links = element.find_elements(By.TAG_NAME, "a")
                    if not links:
                        continue

                    url = None
                    for link in links:
                        href = link.get_attribute("href")
                        if href and ("/job/" in href or "/careers/" in href or "rid=" in href):
                            url = href
                            break

                    if not url:
                        continue

                    # Extract job ID from URL
                    job_id = self._extract_job_id_from_url(url)
                    if not job_id or job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)

                    # Extract title
                    title = ""
                    try:
                        # Try various title selectors
                        for selector in ["h3", "h2", "[class*='title']", "[class*='heading']"]:
                            title_elements = element.find_elements(By.CSS_SELECTOR, selector)
                            if title_elements:
                                title = title_elements[0].text.strip()
                                if title:
                                    break

                        # Fallback to link text
                        if not title:
                            for link in links:
                                link_text = link.text.strip()
                                if link_text and len(link_text) > 5:
                                    title = link_text
                                    break
                    except Exception:
                        pass

                    if not title:
                        title = "Tesla Position"

                    # Extract location
                    location = "United States"
                    try:
                        location_elements = element.find_elements(By.CSS_SELECTOR, "[class*='location']")
                        if location_elements:
                            loc_text = location_elements[0].text.strip()
                            if loc_text:
                                location = loc_text
                    except Exception:
                        pass

                    # Extract tags/category
                    tags = []
                    try:
                        tag_elements = element.find_elements(By.CSS_SELECTOR, "[class*='tag'], [class*='category'], [class*='department']")
                        for tag_elem in tag_elements:
                            tag_text = tag_elem.text.strip()
                            if tag_text:
                                tags.append(tag_text)
                    except Exception:
                        pass

                    raw_id = job_id
                    uid = Job.generate_uid(self.source_group, raw_id=raw_id)

                    jobs.append(
                        Job(
                            uid=uid,
                            source_group=self.source_group,
                            source_name=self.source_name,
                            title=title,
                            company="Tesla",
                            location=location,
                            url=url,
                            raw_id=raw_id,
                            tags=tags,
                        )
                    )
                except Exception as e:
                    # Skip individual cards that fail to parse
                    logger.debug(f"Tesla: failed to parse job element: {e}")
                    continue

        except Exception as e:
            logger.warning("Tesla: DOM extraction error: %s", e)

        return jobs

    def _extract_job_id_from_url(self, url: str) -> Optional[str]:
        """Extract job ID from Tesla job URL."""
        # Try different patterns
        patterns = [
            r'/job/(\d+)',
            r'rid=(\d+)',
            r'/careers/job/(\d+)',
            r'id=(\d+)',
            r'/position/(\d+)',
            r'/(\d{5,})',  # Generic 5+ digit number
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        # Fallback: use URL hash
        import hashlib
        return hashlib.md5(url.encode()).hexdigest()[:16]

    def _parse_jobs_from_html(self, html: str) -> list[Job]:
        """Parse jobs from HTML as fallback when DOM parsing fails."""
        jobs = []
        seen_ids = set()

        # Pattern to match Tesla/Taleo job links
        patterns = [
            # Taleo requisition format
            r'href=["\']([^"\']*requisition\.jsp[^"\']*[?&]rid=(\d+)[^"\']*)["\']',
            # Direct job/careers links
            r'href=["\']([^"\']*(?:/job/|/careers/)([^"\'/?]+)[^"\']*)["\']',
            # Generic ID parameter
            r'href=["\']([^"\']*[?&](?:id|jobId|req)=(\d+)[^"\']*)["\']',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for url, job_id in matches:
                # Skip invalid job IDs
                if not job_id or job_id in seen_ids or not job_id.isdigit():
                    continue
                seen_ids.add(job_id)

                # Build full URL if relative
                if not url.startswith("http"):
                    if url.startswith("/"):
                        # Determine base URL
                        if "taleo.net" in url or "cho.tbe" in url:
                            url = f"https://cho.tbe.taleo.net{url}"
                        else:
                            url = f"https://www.tesla.com{url}"
                    else:
                        url = f"https://www.tesla.com/{url}"

                # Extract title - try multiple approaches
                title = "Tesla Position"

                # Approach 1: Look for link text containing the job ID
                # Match: <a href="...rid=12345...">TITLE TEXT</a>
                link_text_pattern = rf'href=["\'][^"\']*{re.escape(job_id)}[^"\']*["\'][^>]*>([^<]+)</a>'
                link_match = re.search(link_text_pattern, html, re.IGNORECASE)
                if link_match:
                    potential_title = link_match.group(1).strip()
                    if len(potential_title) > 3:
                        title = potential_title

                # Approach 2: Look in context around the job ID
                if title == "Tesla Position":
                    # Find position of this job ID in HTML
                    job_id_pos = html.find(job_id)
                    if job_id_pos != -1:
                        context_start = max(0, job_id_pos - 300)
                        context_end = min(len(html), job_id_pos + 300)
                        context = html[context_start:context_end]

                        title_patterns = [
                            r'>([^<]{15,150})</a>',  # Link text
                            r'<(?:td|span|div)[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</',
                            r'<h[1-6][^>]*>([^<]+)</h[1-6]>',
                        ]

                        for tp in title_patterns:
                            tm = re.search(tp, context, re.IGNORECASE)
                            if tm:
                                potential_title = tm.group(1).strip()
                                # Valid title should be reasonable length and not just whitespace/numbers
                                if (15 <= len(potential_title) <= 150 and
                                    not potential_title.isdigit() and
                                    any(c.isalpha() for c in potential_title)):
                                    title = potential_title
                                    break

                title = re.sub(r'\s+', ' ', title).strip()

                raw_id = job_id
                uid = Job.generate_uid(self.source_group, raw_id=raw_id)

                jobs.append(Job(
                    uid=uid,
                    source_group=self.source_group,
                    source_name=self.source_name,
                    title=title,
                    company="Tesla",
                    location="United States",
                    url=url,
                    raw_id=raw_id,
                    tags=[],
                ))

        return jobs

    def _is_akamai_blocked(self, html: str) -> bool:
        """Check if the page was blocked by Akamai protection."""
        akamai_indicators = [
            "Access Denied",
            "Reference #",
            "errors.edgesuite.net",
            "You don't have permission to access",
        ]
        return any(indicator in html for indicator in akamai_indicators)

    def _matches_filters(self, job: Job) -> bool:
        """Check if job matches configured filters.

        Filters jobs based on keywords in title, snippet, and tags.
        Useful for focusing on new grad/early career positions.
        """
        if not self._filter_keywords:
            return True

        # Combine searchable text
        searchable = " ".join([
            job.title.lower(),
            job.snippet.lower(),
            " ".join(job.tags).lower(),
        ])

        # Check if any filter keyword matches
        return any(keyword.lower() in searchable for keyword in self._filter_keywords)
