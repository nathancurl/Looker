"""Tests for Greenhouse fetcher."""

import json

import responses

from fetchers.greenhouse import GreenhouseFetcher


class TestGreenhouseFetcher:
    @responses.activate
    def test_fetch_jobs(self, load_fixture):
        fixture = load_fixture("greenhouse_response.json")
        responses.add(
            responses.GET,
            "https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true",
            json=fixture,
            status=200,
        )

        fetcher = GreenhouseFetcher({"name": "Acme-GH", "board_token": "acme", "company": "Acme"})
        jobs = fetcher.fetch()

        assert len(jobs) == 2
        assert jobs[0].title == "Software Engineer, Backend"
        assert jobs[0].uid == "greenhouse:4012345"
        assert jobs[0].company == "Acme"
        assert "backend engineer" in jobs[0].snippet.lower()

    @responses.activate
    def test_empty_response(self):
        responses.add(
            responses.GET,
            "https://boards-api.greenhouse.io/v1/boards/empty/jobs?content=true",
            json={"jobs": []},
            status=200,
        )

        fetcher = GreenhouseFetcher({"name": "Empty", "board_token": "empty"})
        jobs = fetcher.fetch()
        assert jobs == []

    @responses.activate
    def test_safe_fetch_on_error(self):
        responses.add(
            responses.GET,
            "https://boards-api.greenhouse.io/v1/boards/broken/jobs?content=true",
            json={"error": "not found"},
            status=404,
        )

        fetcher = GreenhouseFetcher({"name": "Broken", "board_token": "broken"})
        jobs = fetcher.safe_fetch()
        assert jobs == []
