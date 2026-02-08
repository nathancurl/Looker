"""Browser-based fetcher for Tesla Jobs (Playwright implementation).

This fetcher uses Playwright to bypass Akamai protection by automating
a real browser instead of making direct HTTP requests.

Requirements:
    pip install playwright
    playwright install chromium

Usage:
    from fetchers.tesla_browser import TeslaBrowserFetcher

    config = {
        "name": "Tesla",
        "company": "Tesla",
        "headless": True,  # Set to False for debugging
        "timeout": 30000,
        "filter_keywords": ["software engineer", "new grad"]
    }

    fetcher = TeslaBrowserFetcher(config)
    jobs = fetcher.safe_fetch()
"""

import logging
import re
from typing import Optional
from datetime import datetime

from fetchers.base import BaseFetcher
from models import Job

logger = logging.getLogger(__name__)

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning(
        "Playwright not installed. Install with: pip install playwright && playwright install chromium"
    )


class TeslaBrowserFetcher(BaseFetcher):
    """Fetcher for Tesla jobs using browser automation via Playwright.

    This fetcher bypasses anti-bot protection by using a real browser
    instance instead of direct HTTP requests.
    """

    source_group = "tesla"

    def __init__(self, source_config: dict):
        super().__init__(source_config)
        self._headless = source_config.get("headless", True)
        self._timeout = source_config.get("timeout", 30000)  # 30 seconds
        self._filter_keywords = source_config.get("filter_keywords", [])
        self._max_jobs = source_config.get("max_jobs", 100)

        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright is required for TeslaBrowserFetcher. "
                "Install with: pip install playwright && playwright install chromium"
            )

    def fetch(self) -> list[Job]:
        """Fetch Tesla jobs using Playwright browser automation."""
        jobs = []

        with sync_playwright() as p:
            # Launch browser with anti-detection settings
            browser = p.chromium.launch(
                headless=self._headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-web-security',
                ]
            )

            # Create context with realistic settings
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='en-US',
                timezone_id='America/Los_Angeles',
                extra_http_headers={
                    'Accept-Language': 'en-US,en;q=0.9',
                }
            )

            page = context.new_page()

            try:
                logger.info("Navigating to Tesla careers page...")
                page.goto('https://www.tesla.com/careers/search', timeout=self._timeout)

                # Wait for page to load - adjust selector based on actual page structure
                logger.info("Waiting for job listings to load...")
                try:
                    # Try multiple possible selectors
                    page.wait_for_selector(
                        'a[href*="careers"], .job-listing, [data-job], .requisition',
                        timeout=self._timeout
                    )
                except PlaywrightTimeout:
                    logger.warning("Job listings did not load within timeout")
                    # Take screenshot for debugging if not headless
                    if not self._headless:
                        page.screenshot(path='tesla_timeout.png')

                # Extract job listings
                logger.info("Extracting job data...")
                jobs = self._extract_jobs_from_page(page)

                # Filter by keywords if configured
                if self._filter_keywords:
                    jobs = [j for j in jobs if self._matches_filters(j)]

                # Limit to max_jobs
                jobs = jobs[:self._max_jobs]

            except Exception as e:
                logger.error("Error fetching Tesla jobs with browser: %s", e)
                # Take screenshot for debugging if not headless
                if not self._headless:
                    try:
                        page.screenshot(path='tesla_error.png')
                    except:
                        pass
                raise
            finally:
                browser.close()

        return jobs

    def _extract_jobs_from_page(self, page) -> list[Job]:
        """Extract job listings from the page.

        This method attempts multiple extraction strategies since Tesla's
        page structure may vary.
        """
        jobs = []

        # Strategy 1: Extract via JavaScript evaluation
        try:
            job_data = page.evaluate('''() => {
                // Try to find job elements by common patterns
                const selectors = [
                    'a[href*="/careers/"]',
                    '.job-listing',
                    '[data-job-id]',
                    '.requisition',
                    'article[class*="job"]'
                ];

                let jobElements = [];
                for (const selector of selectors) {
                    jobElements = document.querySelectorAll(selector);
                    if (jobElements.length > 0) break;
                }

                return Array.from(jobElements).map(el => {
                    // Extract job information
                    const link = el.tagName === 'A' ? el : el.querySelector('a');
                    const titleEl = el.querySelector('[class*="title"], h2, h3, strong');
                    const locationEl = el.querySelector('[class*="location"], [class*="city"]');

                    return {
                        title: titleEl?.textContent?.trim() || el.textContent?.split('\\n')[0]?.trim() || '',
                        location: locationEl?.textContent?.trim() || '',
                        url: link?.href || '',
                        text: el.textContent?.trim() || ''
                    };
                }).filter(job => job.title && job.url);
            }''')

            for item in job_data:
                job = self._create_job_from_data(item)
                if job:
                    jobs.append(job)

        except Exception as e:
            logger.warning("JavaScript extraction failed: %s", e)

        # Strategy 2: Parse links if JS extraction failed
        if not jobs:
            jobs = self._extract_jobs_from_links(page)

        return jobs

    def _extract_jobs_from_links(self, page) -> list[Job]:
        """Fallback: Extract jobs from all career-related links on page."""
        jobs = []
        seen_urls = set()

        try:
            # Get all links that might be jobs
            links = page.query_selector_all('a[href*="careers"], a[href*="job"], a[href*="requisition"]')

            for link in links:
                try:
                    url = link.get_attribute('href')
                    if not url or url in seen_urls:
                        continue

                    # Make URL absolute
                    if url.startswith('/'):
                        url = f"https://www.tesla.com{url}"

                    seen_urls.add(url)

                    # Get link text as title
                    title = link.text_content().strip()
                    if not title or len(title) < 5:
                        continue

                    # Try to find location near the link
                    location = "United States"  # Default
                    parent = link.evaluate('el => el.parentElement')
                    if parent:
                        parent_text = link.evaluate('el => el.parentElement.textContent')
                        # Look for location patterns
                        loc_match = re.search(
                            r'\b([\w\s]+,\s*[A-Z]{2}|California|Texas|Nevada|New York)\b',
                            parent_text
                        )
                        if loc_match:
                            location = loc_match.group(1)

                    job = self._create_job_from_data({
                        'title': title,
                        'url': url,
                        'location': location,
                        'text': title
                    })

                    if job:
                        jobs.append(job)

                except Exception as e:
                    logger.debug("Error extracting job from link: %s", e)
                    continue

        except Exception as e:
            logger.warning("Link extraction failed: %s", e)

        return jobs

    def _create_job_from_data(self, data: dict) -> Optional[Job]:
        """Create a Job object from extracted data."""
        try:
            url = data.get('url', '')
            title = data.get('title', '')

            if not url or not title:
                return None

            # Extract job ID from URL
            # URLs might be like: /careers/search/job/12345 or requisition.jsp?rid=12345
            job_id = None
            rid_match = re.search(r'rid=(\d+)', url)
            if rid_match:
                job_id = rid_match.group(1)
            else:
                job_match = re.search(r'/job/(\d+)', url)
                if job_match:
                    job_id = job_match.group(1)

            # Generate UID
            if job_id:
                raw_id = f"tesla:{job_id}"
                uid = Job.generate_uid(self.source_group, raw_id=raw_id)
            else:
                uid = Job.generate_uid(self.source_group, url=url)
                raw_id = None

            location = data.get('location', 'United States')
            snippet = data.get('text', '')[:300]  # Limit snippet

            return Job(
                uid=uid,
                source_group=self.source_group,
                source_name=self.source_name,
                title=title,
                company=self._config.get("company", "Tesla"),
                location=location,
                url=url,
                snippet=snippet,
                raw_id=raw_id,
                tags=[],
            )

        except Exception as e:
            logger.warning("Failed to create job from data: %s", e)
            return None

    def _matches_filters(self, job: Job) -> bool:
        """Check if job matches configured keyword filters."""
        if not self._filter_keywords:
            return True

        searchable = " ".join([
            job.title.lower(),
            job.snippet.lower(),
            " ".join(job.tags).lower(),
        ])

        return any(keyword.lower() in searchable for keyword in self._filter_keywords)


# Example usage and testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    config = {
        "name": "Tesla (Browser)",
        "company": "Tesla",
        "headless": False,  # Set to True for production
        "timeout": 30000,
        "max_jobs": 50,
        "filter_keywords": [
            "software engineer",
            "software developer",
            "engineer",
            "developer"
        ]
    }

    fetcher = TeslaBrowserFetcher(config)
    jobs = fetcher.safe_fetch()

    print(f"\nFetched {len(jobs)} jobs:")
    for job in jobs[:10]:  # Show first 10
        print(f"\n- {job.title}")
        print(f"  Location: {job.location}")
        print(f"  URL: {job.url}")
