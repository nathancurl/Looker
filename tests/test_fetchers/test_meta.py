"""Tests for Meta fetcher."""

import responses

from fetchers.meta import MetaFetcher

CAREERS_URL = "https://www.metacareers.com/jobs"
GRAPHQL_URL = "https://www.metacareers.com/api/graphql/"

# Minimal HTML containing an LSD token
LSD_PAGE = '<input type="hidden" name="lsd" value="test-lsd-token" />'


class TestMetaFetcher:
    @responses.activate
    def test_fetch_jobs(self, load_fixture):
        # Step 1: Careers page with LSD token
        responses.add(
            responses.GET,
            CAREERS_URL,
            body=LSD_PAGE,
            status=200,
        )
        # Step 2: GraphQL response
        fixture = load_fixture("meta_graphql_response.json")
        responses.add(
            responses.POST,
            GRAPHQL_URL,
            json=fixture,
            status=200,
        )

        fetcher = MetaFetcher(
            {"name": "Meta", "company": "Meta", "doc_id": "fake_doc_id_123"}
        )
        jobs = fetcher.fetch()

        assert len(jobs) == 2
        assert jobs[0].title == "Software Engineer, Infrastructure"
        assert jobs[0].uid == "maang:meta:META001"
        assert jobs[0].company == "Meta"
        assert "Menlo Park" in jobs[0].location
        assert "infrastructure" in jobs[0].snippet.lower()

        # Multi-location
        assert "New York" in jobs[1].location
        assert "Menlo Park" in jobs[1].location

    @responses.activate
    def test_empty_when_no_doc_id(self):
        """Returns [] when doc_id is not configured."""
        fetcher = MetaFetcher({"name": "Meta", "company": "Meta", "doc_id": ""})
        jobs = fetcher.fetch()
        assert jobs == []

    @responses.activate
    def test_safe_fetch_on_error(self):
        """Returns [] when session init fails."""
        responses.add(
            responses.GET,
            CAREERS_URL,
            body="Forbidden",
            status=403,
        )

        fetcher = MetaFetcher(
            {"name": "Meta", "company": "Meta", "doc_id": "some_doc_id"}
        )
        jobs = fetcher.safe_fetch()
        assert jobs == []
