"""Tests for Lever fetcher."""

import responses

from fetchers.lever import LeverFetcher


class TestLeverFetcher:
    @responses.activate
    def test_fetch_jobs(self, load_fixture):
        fixture = load_fixture("lever_response.json")
        responses.add(
            responses.GET,
            "https://api.lever.co/v0/postings/acme?mode=json",
            json=fixture,
            status=200,
        )

        fetcher = LeverFetcher({"name": "Acme-Lever", "slug": "acme", "company": "Acme"})
        jobs = fetcher.fetch()

        assert len(jobs) == 2
        assert jobs[0].title == "Junior Software Engineer"
        assert jobs[0].location == "Remote, US"
        assert jobs[0].posted_at is not None

    @responses.activate
    def test_empty_list(self):
        responses.add(
            responses.GET,
            "https://api.lever.co/v0/postings/empty?mode=json",
            json=[],
            status=200,
        )

        fetcher = LeverFetcher({"name": "Empty", "slug": "empty"})
        jobs = fetcher.fetch()
        assert jobs == []
