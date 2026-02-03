"""Tests for HN Hiring fetcher."""

from unittest.mock import patch

from fetchers.hnhiring import HNHiringFetcher


SAMPLE_FEED = {
    "entries": [
        {
            "title": "Acme Corp | Backend Engineer | Remote | Python",
            "link": "https://news.ycombinator.com/item?id=12345",
            "description": "Acme Corp | Backend Engineer | Remote | Python, PostgreSQL",
            "summary": "",
        },
        {
            "title": "StartupX | Full Stack | SF",
            "link": "https://news.ycombinator.com/item?id=12346",
            "description": "StartupX | Full Stack Developer | San Francisco | React, Node.js",
            "summary": "",
        },
    ],
    "bozo": False,
}


class TestHNHiringFetcher:
    @patch("fetchers.hnhiring.feedparser.parse")
    def test_fetch_jobs(self, mock_parse):
        mock_parse.return_value = type("Feed", (), {
            "entries": SAMPLE_FEED["entries"],
            "bozo": False,
        })()

        fetcher = HNHiringFetcher({"name": "HN-Hiring", "feed_url": "https://hnrss.org/whoishiring/jobs"})
        jobs = fetcher.fetch()

        assert len(jobs) == 2
        assert jobs[0].company == "Acme Corp"
        assert jobs[0].title == "Backend Engineer"
        assert jobs[0].url == "https://news.ycombinator.com/item?id=12345"

    @patch("fetchers.hnhiring.feedparser.parse")
    def test_empty_feed(self, mock_parse):
        mock_parse.return_value = type("Feed", (), {
            "entries": [],
            "bozo": False,
        })()

        fetcher = HNHiringFetcher({"name": "HN-Hiring"})
        jobs = fetcher.fetch()
        assert jobs == []
