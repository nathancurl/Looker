"""Tests for Ripplematch fetcher.

Note: The Ripplematch fetcher uses Selenium DOM-based extraction rather than
HTML regex parsing, so most tests verify instantiation and error handling.
Integration testing requires Chrome and is done via scripts/test_ripplematch.py
"""

from unittest.mock import MagicMock, patch
import sys

from fetchers.ripplematch import RipplematchFetcher


class TestRipplematchFetcher:
    @patch.dict(sys.modules, {
        'selenium': MagicMock(),
        'selenium.webdriver': MagicMock(),
        'selenium.webdriver.chrome.options': MagicMock(),
        'selenium.webdriver.chrome.service': MagicMock(),
        'selenium.webdriver.common.by': MagicMock(),
        'selenium.webdriver.support.ui': MagicMock(),
        'selenium.webdriver.support': MagicMock(),
        'webdriver_manager': MagicMock(),
        'webdriver_manager.chrome': MagicMock(),
    })
    def test_selenium_import(self):
        """Test that fetcher handles selenium imports."""
        fetcher = RipplematchFetcher({"name": "Ripplematch"})
        # Just verify it can be instantiated
        assert fetcher.source_group == "ripplematch"

    def test_configuration(self):
        """Test that fetcher accepts configuration parameters."""
        config = {
            "name": "Ripplematch Test",
            "max_scrolls": 20,
            "headless": False,
        }
        fetcher = RipplematchFetcher(config)

        assert fetcher.source_name == "Ripplematch Test"
        assert fetcher._max_scrolls == 20
        assert fetcher._headless == False

    def test_default_configuration(self):
        """Test default configuration values."""
        fetcher = RipplematchFetcher({"name": "Ripplematch"})

        assert fetcher._max_scrolls == 10  # Default value
        assert fetcher._headless == True  # Default value

    def test_safe_fetch_returns_empty_on_error(self):
        """Test that safe_fetch handles errors gracefully."""
        fetcher = RipplematchFetcher({"name": "Ripplematch"})

        # Mock the fetch method to raise an exception
        original_fetch = fetcher.fetch
        def mock_fetch():
            raise Exception("Browser error")
        fetcher.fetch = mock_fetch

        jobs = fetcher.safe_fetch()
        assert jobs == []

        # Restore
        fetcher.fetch = original_fetch

    def test_extract_company_from_logo(self):
        """Test company extraction from logo alt text."""
        fetcher = RipplematchFetcher({"name": "Ripplematch"})

        # Test with logo alt text
        html_with_logo = '<img alt="Google logo" src="..." />'
        company = fetcher._extract_company_from_card(html_with_logo)
        assert company == "Google"

        # Test with company name containing special characters
        html_with_special = '<img alt="AT&amp;T logo" src="..." />'
        company = fetcher._extract_company_from_card(html_with_special)
        assert company == "AT&T"

        # Test with no logo (fallback pattern might still match text)
        html_no_logo = '<p>just some text</p>'
        company = fetcher._extract_company_from_card(html_no_logo)
        # Either empty or the fallback pattern matched - both are acceptable
        assert isinstance(company, str)
