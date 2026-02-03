"""Tests for Netflix fetcher."""

import responses

from fetchers.netflix import NetflixFetcher

BASE_URL = "https://explore.jobs.netflix.net/api/apply/v2/jobs"


class TestNetflixFetcher:
    @responses.activate
    def test_fetch_jobs(self, load_fixture):
        fixture = load_fixture("netflix_response.json")
        responses.add(
            responses.GET,
            BASE_URL,
            json=fixture,
            status=200,
        )

        fetcher = NetflixFetcher({"name": "Netflix", "company": "Netflix"})
        jobs = fetcher.fetch()

        assert len(jobs) == 2
        assert jobs[0].title == "Software Engineer, Platform"
        assert jobs[0].uid == "maang:netflix:790312512674"
        assert jobs[0].company == "Netflix"
        assert jobs[0].location == "Los Gatos, CA"
        assert "Engineering" in jobs[0].tags

    @responses.activate
    def test_empty_response(self):
        responses.add(
            responses.GET,
            BASE_URL,
            json={"count": 0, "positions": []},
            status=200,
        )

        fetcher = NetflixFetcher({"name": "Netflix", "company": "Netflix"})
        jobs = fetcher.fetch()
        assert jobs == []

    @responses.activate
    def test_safe_fetch_on_error(self):
        responses.add(
            responses.GET,
            BASE_URL,
            json={"error": "forbidden"},
            status=403,
        )

        fetcher = NetflixFetcher({"name": "Netflix", "company": "Netflix"})
        jobs = fetcher.safe_fetch()
        assert jobs == []
