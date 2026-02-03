"""Tests for Jobvite fetcher."""

import responses

from fetchers.jobvite import JobviteFetcher


class TestJobviteFetcher:
    @responses.activate
    def test_fetch_jobs(self, load_fixture):
        fixture = load_fixture("jobvite_response.json")
        responses.add(
            responses.GET,
            "https://jobs.jobvite.com/api/v2/acme/jobs",
            json=fixture,
            status=200,
        )

        fetcher = JobviteFetcher(
            {"name": "Acme", "company_id": "acme", "company": "Acme Corp"}
        )
        jobs = fetcher.fetch()

        assert len(jobs) == 2
        assert jobs[0].title == "Software Engineer"
        assert jobs[0].uid == "jobvite:acme:JV001"
        assert jobs[0].company == "Acme Corp"
        assert jobs[0].location == "San Francisco, CA"
        assert "Engineering" in jobs[0].tags
        assert "scalable web" in jobs[0].snippet.lower()
        assert jobs[0].posted_at is not None

    @responses.activate
    def test_empty_response(self):
        responses.add(
            responses.GET,
            "https://jobs.jobvite.com/api/v2/empty/jobs",
            json={"requisitions": []},
            status=200,
        )

        fetcher = JobviteFetcher({"name": "Empty", "company_id": "empty", "company": "Empty"})
        jobs = fetcher.fetch()
        assert jobs == []

    @responses.activate
    def test_safe_fetch_on_error(self):
        responses.add(
            responses.GET,
            "https://jobs.jobvite.com/api/v2/broken/jobs",
            body="Not Found",
            status=404,
        )

        fetcher = JobviteFetcher({"name": "Broken", "company_id": "broken", "company": "Broken"})
        jobs = fetcher.safe_fetch()
        assert jobs == []
