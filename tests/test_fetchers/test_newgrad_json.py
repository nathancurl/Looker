"""Tests for NewGrad JSON fetcher."""

import responses

from fetchers.newgrad_json import NewGradJSONFetcher


class TestNewGradJSONFetcher:
    @responses.activate
    def test_fetch_filters_inactive(self, load_fixture):
        fixture = load_fixture("newgrad_json_response.json")
        url = "https://raw.githubusercontent.com/vanshb03/New-Grad-2026/dev/.github/scripts/listings.json"
        responses.add(responses.GET, url, json=fixture, status=200)

        fetcher = NewGradJSONFetcher({
            "name": "vanshb03-New-Grad-2026",
            "owner": "vanshb03",
            "repo": "New-Grad-2026",
            "branch": "dev",
            "json_path": ".github/scripts/listings.json",
        })
        jobs = fetcher.fetch()

        # Only the first entry is active+visible
        assert len(jobs) == 1
        assert jobs[0].company == "TechCo"
        assert jobs[0].title == "Software Engineer, New Grad"
        assert jobs[0].uid == "newgrad:ng-uuid-001"
        assert jobs[0].location == "San Francisco, CA"
        assert "sponsorship:Will Sponsor" in jobs[0].tags

    @responses.activate
    def test_fetch_all_inactive(self):
        url = "https://raw.githubusercontent.com/test/repo/dev/listings.json"
        responses.add(
            responses.GET, url,
            json=[{"id": "1", "active": False, "is_visible": True, "title": "T", "company_name": "C", "url": "u", "locations": []}],
            status=200,
        )

        fetcher = NewGradJSONFetcher({
            "name": "test",
            "owner": "test",
            "repo": "repo",
            "branch": "dev",
            "json_path": "listings.json",
        })
        jobs = fetcher.fetch()
        assert jobs == []
