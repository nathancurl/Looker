"""Shared Selenium utilities for fetchers that use browser automation.

Provides a thread-safe way to get a ChromeDriver service without the
race conditions that occur when multiple threads use ChromeDriverManager
simultaneously (concurrent downloads corrupt the zip file).
"""

import logging
import os
import shutil
import threading

logger = logging.getLogger(__name__)

_chromedriver_path: str | None = None
_lock = threading.Lock()

# Well-known cache locations for webdriver-manager
_WDM_CACHE_PATHS = [
    os.path.expanduser("~/.wdm/drivers/chromedriver/linux64"),
    os.path.expanduser("~/.wdm/drivers/chromedriver/mac64"),
    os.path.expanduser("~/.wdm/drivers/chromedriver/mac-arm64"),
]


def _find_cached_chromedriver() -> str | None:
    """Search the webdriver-manager cache for a usable chromedriver binary."""
    for cache_dir in _WDM_CACHE_PATHS:
        if not os.path.isdir(cache_dir):
            continue
        # Walk version subdirectories, prefer newest
        try:
            versions = sorted(os.listdir(cache_dir), reverse=True)
        except OSError:
            continue
        for version in versions:
            # Check nested path (newer WDM format)
            nested = os.path.join(cache_dir, version, "chromedriver-linux64", "chromedriver")
            if os.path.isfile(nested) and os.access(nested, os.X_OK):
                return nested
            # Check flat path (older WDM format)
            flat = os.path.join(cache_dir, version, "chromedriver")
            if os.path.isfile(flat) and os.access(flat, os.X_OK):
                return flat
    return None


def _find_system_chromedriver() -> str | None:
    """Check if chromedriver is available on PATH."""
    return shutil.which("chromedriver")


def get_chrome_service():
    """Get a Selenium Chrome Service with a valid chromedriver.

    Resolution order:
    1. Cached chromedriver from webdriver-manager cache (no download needed)
    2. System chromedriver on PATH
    3. Fall back to ChromeDriverManager (single-threaded download with lock)

    Returns:
        selenium.webdriver.chrome.service.Service instance
    """
    from selenium.webdriver.chrome.service import Service

    global _chromedriver_path

    # Fast path: already resolved
    if _chromedriver_path and os.path.isfile(_chromedriver_path):
        return Service(executable_path=_chromedriver_path)

    with _lock:
        # Double-check after acquiring lock
        if _chromedriver_path and os.path.isfile(_chromedriver_path):
            return Service(executable_path=_chromedriver_path)

        # Try 1: WDM cache
        path = _find_cached_chromedriver()
        if path:
            logger.info("Using cached chromedriver: %s", path)
            _chromedriver_path = path
            return Service(executable_path=path)

        # Try 2: System chromedriver
        path = _find_system_chromedriver()
        if path:
            logger.info("Using system chromedriver: %s", path)
            _chromedriver_path = path
            return Service(executable_path=path)

        # Try 3: Download via ChromeDriverManager (under lock, so only one thread downloads)
        logger.info("No cached chromedriver found, downloading via ChromeDriverManager...")
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            path = ChromeDriverManager().install()
            logger.info("Downloaded chromedriver to: %s", path)
            _chromedriver_path = path
            return Service(executable_path=path)
        except Exception as e:
            logger.error("Failed to get chromedriver: %s", e)
            raise
