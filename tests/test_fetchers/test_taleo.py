"""Tests for Taleo fetcher."""

import responses

from fetchers.taleo import TaleoFetcher


class TestTaleoFetcher:
    @responses.activate
    def test_fetch_jobs(self, load_fixture):
        fixture = load_fixture("taleo_response.json")
        responses.add(
            responses.GET,
            "https://oracle.taleo.net/requisition/searchRequisitions",
            json=fixture,
            status=200,
        )

        fetcher = TaleoFetcher(
            {"name": "Oracle", "base_url": "https://oracle.taleo.net", "company": "Oracle"}
        )
        jobs = fetcher.fetch()

        assert len(jobs) == 2
        assert jobs[0].title == "Associate Software Engineer"
        assert jobs[0].uid == "taleo:TAL001"
        assert jobs[0].company == "Oracle"
        assert jobs[0].location == "Redwood City, CA, USA"
        assert "Engineering" in jobs[0].tags
        assert "entry-level" in jobs[0].snippet.lower()
        assert jobs[0].posted_at is not None

        # Second job uses alternative field names
        assert jobs[1].title == "New Grad Developer"
        assert "Software Development" in jobs[1].tags

    @responses.activate
    def test_empty_response(self):
        responses.add(
            responses.GET,
            "https://empty.taleo.net/requisition/searchRequisitions",
            json={"total": 0, "requisitions": []},
            status=200,
        )

        fetcher = TaleoFetcher(
            {"name": "Empty", "base_url": "https://empty.taleo.net", "company": "Empty"}
        )
        jobs = fetcher.fetch()
        assert jobs == []

    @responses.activate
    def test_safe_fetch_on_error(self):
        responses.add(
            responses.GET,
            "https://broken.taleo.net/requisition/searchRequisitions",
            body="Service Unavailable",
            status=503,
        )

        fetcher = TaleoFetcher(
            {"name": "Broken", "base_url": "https://broken.taleo.net", "company": "Broken"}
        )
        jobs = fetcher.safe_fetch()
        assert jobs == []
