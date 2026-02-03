"""Tests for Workday fetcher."""

import responses

from fetchers.workday import WorkdayFetcher


class TestWorkdayFetcher:
    @responses.activate
    def test_fetch_jobs(self, load_fixture):
        fixture = load_fixture("workday_response.json")
        base_url = "https://acme.wd5.myworkdayjobs.com/wday/cxs/acme/careers/jobs"
        responses.add(
            responses.POST,
            base_url,
            json=fixture,
            status=200,
        )

        fetcher = WorkdayFetcher(
            {"name": "Acme-Workday", "base_url": base_url, "company": "Acme"}
        )
        jobs = fetcher.fetch()

        assert len(jobs) == 1
        assert jobs[0].title == "Software Developer"
        assert jobs[0].location == "Seattle, WA"
        assert "Entry Level" in jobs[0].snippet
        assert jobs[0].posted_at is not None
        assert "acme.wd5.myworkdayjobs.com" in jobs[0].url

    @responses.activate
    def test_empty_response(self):
        base_url = "https://empty.wd1.myworkdayjobs.com/wday/cxs/empty/careers/jobs"
        responses.add(
            responses.POST,
            base_url,
            json={"total": 0, "jobPostings": []},
            status=200,
        )

        fetcher = WorkdayFetcher({"name": "Empty", "base_url": base_url, "company": "Empty"})
        jobs = fetcher.fetch()
        assert jobs == []
