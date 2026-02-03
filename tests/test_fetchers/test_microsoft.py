"""Tests for Microsoft fetcher."""

import responses

from fetchers.microsoft import MicrosoftFetcher

BASE_URL = "https://gcsservices.careers.microsoft.com/search/api/v1/search"


class TestMicrosoftFetcher:
    @responses.activate
    def test_fetch_jobs(self, load_fixture):
        fixture = load_fixture("microsoft_response.json")
        responses.add(
            responses.GET,
            BASE_URL,
            json=fixture,
            status=200,
        )

        fetcher = MicrosoftFetcher({"name": "Microsoft", "company": "Microsoft"})
        jobs = fetcher.fetch()

        assert len(jobs) == 2
        assert jobs[0].title == "Software Engineer"
        assert jobs[0].uid == "maang:microsoft:MS-100001"
        assert jobs[0].company == "Microsoft"
        assert jobs[0].location == "Redmond, WA"
        assert "jobs.careers.microsoft.com" in jobs[0].url
        assert "azure" in jobs[0].snippet.lower()

    @responses.activate
    def test_empty_response(self):
        responses.add(
            responses.GET,
            BASE_URL,
            json={"operationResult": {"result": {"totalJobs": 0, "jobs": []}}},
            status=200,
        )

        fetcher = MicrosoftFetcher({"name": "Microsoft", "company": "Microsoft"})
        jobs = fetcher.fetch()
        assert jobs == []

    @responses.activate
    def test_safe_fetch_on_error(self):
        responses.add(
            responses.GET,
            BASE_URL,
            body="Service Unavailable",
            status=403,
        )

        fetcher = MicrosoftFetcher({"name": "Microsoft", "company": "Microsoft"})
        jobs = fetcher.safe_fetch()
        assert jobs == []
