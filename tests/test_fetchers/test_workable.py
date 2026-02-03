"""Tests for Workable fetcher."""

import responses

from fetchers.workable import WorkableFetcher


class TestWorkableFetcher:
    @responses.activate
    def test_fetch_jobs(self, load_fixture):
        fixture = load_fixture("workable_response.json")
        responses.add(
            responses.GET,
            "https://apply.workable.com/api/v1/widget/accounts/acme",
            json=fixture,
            status=200,
        )

        fetcher = WorkableFetcher({"name": "Acme-Workable", "subdomain": "acme", "company": "Acme"})
        jobs = fetcher.fetch()

        assert len(jobs) == 1
        assert jobs[0].title == "Full Stack Developer"
        assert jobs[0].location == "Austin, TX, US"
        assert jobs[0].uid == "workable:WK001"
