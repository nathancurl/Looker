"""Tests for Amazon fetcher."""

import responses

from fetchers.amazon import AmazonFetcher

BASE_URL = "https://www.amazon.jobs/en/search.json"


class TestAmazonFetcher:
    @responses.activate
    def test_fetch_jobs(self, load_fixture):
        fixture = load_fixture("amazon_response.json")
        responses.add(
            responses.GET,
            BASE_URL,
            json=fixture,
            status=200,
        )

        fetcher = AmazonFetcher({"name": "Amazon", "company": "Amazon"})
        jobs = fetcher.fetch()

        assert len(jobs) == 2
        assert jobs[0].title == "Software Development Engineer"
        assert jobs[0].uid == "maang:amazon:1234567"
        assert jobs[0].company == "Amazon"
        assert jobs[0].location == "Seattle, WA"
        assert "amazon.jobs" in jobs[0].url
        assert "scalable distributed" in jobs[0].snippet.lower()

    @responses.activate
    def test_empty_response(self):
        responses.add(
            responses.GET,
            BASE_URL,
            json={"hits": 0, "jobs": []},
            status=200,
        )

        fetcher = AmazonFetcher({"name": "Amazon", "company": "Amazon"})
        jobs = fetcher.fetch()
        assert jobs == []

    @responses.activate
    def test_safe_fetch_on_error(self):
        responses.add(
            responses.GET,
            BASE_URL,
            json={"error": "bad request"},
            status=403,
        )

        fetcher = AmazonFetcher({"name": "Amazon", "company": "Amazon"})
        jobs = fetcher.safe_fetch()
        assert jobs == []
