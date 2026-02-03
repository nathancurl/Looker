"""Tests for iCIMS fetcher."""

import responses

from fetchers.icims import ICIMSFetcher


class TestICIMSFetcher:
    @responses.activate
    def test_fetch_jobs(self, load_fixture):
        fixture = load_fixture("icims_response.json")
        responses.add(
            responses.GET,
            "https://careers.acme.com/jobs",
            json=fixture,
            status=200,
        )

        fetcher = ICIMSFetcher(
            {"name": "Acme", "portal_url": "https://careers.acme.com", "company": "Acme Corp"}
        )
        jobs = fetcher.fetch()

        assert len(jobs) == 2
        assert jobs[0].title == "Software Engineer I"
        assert jobs[0].uid == "icims:12345"
        assert jobs[0].company == "Acme Corp"
        assert jobs[0].location == "Austin, TX, USA"
        assert "Engineering" in jobs[0].tags
        assert "cutting-edge" in jobs[0].snippet.lower()
        assert jobs[0].posted_at is not None

    @responses.activate
    def test_empty_response(self):
        responses.add(
            responses.GET,
            "https://careers.empty.com/jobs",
            json={"totalPages": 0, "jobs": []},
            status=200,
        )

        fetcher = ICIMSFetcher(
            {"name": "Empty", "portal_url": "https://careers.empty.com", "company": "Empty"}
        )
        jobs = fetcher.fetch()
        assert jobs == []

    @responses.activate
    def test_safe_fetch_on_error(self):
        responses.add(
            responses.GET,
            "https://careers.broken.com/jobs",
            body="Internal Server Error",
            status=500,
        )

        fetcher = ICIMSFetcher(
            {"name": "Broken", "portal_url": "https://careers.broken.com", "company": "Broken"}
        )
        jobs = fetcher.safe_fetch()
        assert jobs == []
