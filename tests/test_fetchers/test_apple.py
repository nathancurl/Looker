"""Tests for Apple fetcher."""

import responses

from fetchers.apple import AppleFetcher

SEARCH_URL = "https://jobs.apple.com/en-us/search"


class TestAppleFetcher:
    @responses.activate
    def test_fetch_jobs(self):
        # Mock the search page with job links embedded in HTML
        html_response = """
        <!doctype html>
        <html>
        <head><title>Jobs at Apple</title></head>
        <body>
            <div class="results">
                <a href="/en-us/details/200001/software-engineer-ios?team=SFTWR">
                    Software Engineer, iOS
                </a>
                <a href="/en-us/details/200001/software-engineer-ios">See details</a>
                <a href="/en-us/details/200002/ml-engineer-siri?team=MLAI">
                    ML Engineer, Siri
                </a>
                <a href="/en-us/details/200002/ml-engineer-siri/locationPicker">Where hiring</a>
            </div>
        </body>
        </html>
        """
        responses.add(
            responses.GET,
            SEARCH_URL,
            body=html_response,
            status=200,
        )

        fetcher = AppleFetcher({"name": "Apple", "company": "Apple"})
        jobs = fetcher.fetch()

        assert len(jobs) == 2
        assert jobs[0].title == "Software Engineer Ios"
        assert jobs[0].uid == "maang:apple:200001"
        assert jobs[0].company == "Apple"
        assert "Software and Services" in jobs[0].tags

        assert jobs[1].title == "Ml Engineer Siri"
        assert "Machine Learning and AI" in jobs[1].tags

    @responses.activate
    def test_empty_response(self):
        html_response = """
        <!doctype html>
        <html>
        <body><div>No jobs found</div></body>
        </html>
        """
        responses.add(
            responses.GET,
            SEARCH_URL,
            body=html_response,
            status=200,
        )

        fetcher = AppleFetcher({"name": "Apple", "company": "Apple"})
        jobs = fetcher.fetch()
        assert jobs == []

    @responses.activate
    def test_safe_fetch_on_error(self):
        responses.add(
            responses.GET,
            SEARCH_URL,
            body="Server Error",
            status=403,
        )

        fetcher = AppleFetcher({"name": "Apple", "company": "Apple"})
        jobs = fetcher.safe_fetch()
        assert jobs == []

    @responses.activate
    def test_pagination(self):
        # Page 1 with next page link
        page1_html = """
        <html>
        <body>
            <a href="/en-us/details/100001/job-one?team=SFTWR">Job One</a>
            <a href="/en-us/search?page=2">Next</a>
        </body>
        </html>
        """
        # Page 2 without next page link
        page2_html = """
        <html>
        <body>
            <a href="/en-us/details/100002/job-two?team=HRDWR">Job Two</a>
        </body>
        </html>
        """

        responses.add(
            responses.GET,
            SEARCH_URL,
            body=page1_html,
            status=200,
        )
        responses.add(
            responses.GET,
            SEARCH_URL,
            body=page2_html,
            status=200,
        )

        fetcher = AppleFetcher({"name": "Apple", "company": "Apple", "max_pages": 5})
        jobs = fetcher.fetch()

        assert len(jobs) == 2
        assert jobs[0].uid == "maang:apple:100001"
        assert jobs[1].uid == "maang:apple:100002"
