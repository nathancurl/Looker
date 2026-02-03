"""Tests for Ashby fetcher."""

import responses

from fetchers.ashby import AshbyFetcher


class TestAshbyFetcher:
    @responses.activate
    def test_fetch_jobs(self, load_fixture):
        fixture = load_fixture("ashby_response.json")
        responses.add(
            responses.GET,
            "https://api.ashbyhq.com/posting-api/job-board/acme",
            json=fixture,
            status=200,
        )

        fetcher = AshbyFetcher({"name": "Acme-Ashby", "clientname": "acme", "company": "Acme"})
        jobs = fetcher.fetch()

        assert len(jobs) == 1
        assert jobs[0].title == "Backend Engineer"
        assert jobs[0].uid == "ashby:ashby-001"
        assert jobs[0].posted_at is not None
