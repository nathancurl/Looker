"""Tests for SmartRecruiters fetcher."""

import responses

from fetchers.smartrecruiters import SmartRecruitersFetcher


class TestSmartRecruitersFetcher:
    @responses.activate
    def test_fetch_jobs(self, load_fixture):
        fixture = load_fixture("smartrecruiters_response.json")
        responses.add(
            responses.GET,
            "https://api.smartrecruiters.com/v1/companies/acme/postings",
            json=fixture,
            status=200,
        )

        fetcher = SmartRecruitersFetcher(
            {"name": "Acme-SR", "company_id": "acme", "company": "Acme"}
        )
        jobs = fetcher.fetch()

        assert len(jobs) == 1
        assert jobs[0].title == "Python Developer"
        assert jobs[0].location == "Chicago, US"
        assert jobs[0].uid == "smartrecruiters:sr-001"
